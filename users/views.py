import socket
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from pi_devices.models import Device
from .forms import UserRegisterForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.http import require_POST, require_http_methods
from django.db import transaction
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from datetime import timedelta
from django.db.models import Prefetch, Q, Count
from groups.models import Group
from django.conf import settings
from django.http import HttpResponseForbidden, Http404
from django.db import models
from django.urls import reverse


@login_required
def offcanvas_groups(request):
    """
    回傳使用者可見的群組清單（側欄 lazy-load 用的 partial，不是整頁）
    對應模板：templates/home/partials/_group_items.html
    """
    groups = (
        Group.objects.filter(
            Q(owner=request.user) | Q(users=request.user)
        )  # 依你的模型調整：users / memberships
        .annotate(device_count=Count("devices", distinct=True))
        .order_by("name", "id")
        .distinct()
    )
    return render(request, "home/partials/_group_items.html", {"groups": groups})


@require_http_methods(["GET", "POST"])
def register_view(request):
    serial = (request.GET.get("serial") or "").strip()
    code = (request.GET.get("code") or "").strip()

    device = None
    if serial and code:
        # 用 iexact 避免大小寫/空白問題
        try:
            device = Device.objects.get(
                serial_number__iexact=serial,
                verification_code__iexact=code,
                is_bound=False,
            )
        except Device.DoesNotExist:
            # 帶了參數但不合法 → 顯示你已有的錯誤頁
            return render(request, "users/register_invalid.html", status=400)

    # === 已登入：綁定模式 ===
    if request.user.is_authenticated:
        if not device:
            # 已登入但沒有有效裝置參數 → 回主要頁
            return redirect("group_list")

        if request.method == "POST":
            # 不再要求 action=bind；只要 POST 就綁
            device.user = request.user
            device.is_bound = True
            device.save(update_fields=["user", "is_bound"])
            request.session.pop("pending_device_bind", None)
            messages.success(request, f"已將裝置 {device.serial_number} 綁定到你的帳號")
            return redirect("my_devices")

        # GET：顯示綁定確認頁
        return render(request, "pi_devices/device_bind.html", {"device": device})

    # 若 query 帶到合法 device，先把 token 存到 session 當備援
    if device:
        request.session["reg_token"] = device.token

    # ★ 把 token 傳進表單；若當下 device 為 None，就用 session 備援
    token = device.token if device else request.session.get("reg_token")
    form = UserRegisterForm(request.POST or None, token=token)

    if request.method == "POST" and form.is_valid():
        user = form.save()  # 表單裡會用 token 完成設備驗證與綁定
        # 🔥 不要在 view 這裡再綁一次，避免重複或競態
        login(request, user)
        messages.success(request, "註冊成功，歡迎！")
        # 綁定成功後清掉備援
        request.session.pop("reg_token", None)
        request.session.pop("pending_device_bind", None)
        return redirect("group_list")

    return render(request, "users/register.html", {"form": form, "device": device})


def is_device_online(ip_address, port=8800, timeout=2):
    try:
        with socket.create_connection((ip_address, port), timeout=timeout):
            return True
    except Exception:
        return False


def login_view(request):
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # HTML 訊息（提醒：模板要用 |safe 才會渲染 HTML）
            role_msg = ""
            if getattr(user, "is_superadmin", False):
                role_msg = '<div style="color:green;">您是 SuperAdmin，可以管理所有設備與使用者。</div>'
            elif getattr(user, "is_admin", False):
                role_msg = '<div style="color:blue;">您是 Admin，擁有管理權限。</div>'
            else:
                role_msg = '<div style="color:gray;">您是一般使用者。</div>'

            html_msg = f"""
                <h2>👋 歡迎回來 {user.email}</h2>
                <p>目前身份：<strong>{getattr(user, 'get_role_display', lambda: 'User')()}</strong></p>
                {role_msg}
            """
            messages.success(request, html_msg)

            # ★ 優先使用 next（POST > GET），並做安全檢查
            nxt = request.POST.get("next") or request.GET.get("next")
            if nxt and url_has_allowed_host_and_scheme(
                nxt, allowed_hosts={request.get_host()}
            ):
                return redirect(nxt)

            # 沒帶 next 就回預設頁（你可改成 group_list）
            return redirect("home")
        else:
            messages.error(request, "帳號或密碼不正確，請再試一次。")

    return render(request, "users/login.html", {"form": form})


@login_required
def home_view(request):
    window = getattr(settings, "DEVICE_ONLINE_WINDOW_SECONDS", 60)
    threshold = timezone.now() - timedelta(seconds=window)

    groups = (
        Group.objects.filter(Q(owner=request.user) | Q(users=request.user))
        .distinct()
        .prefetch_related(
            Prefetch(
                "devices",
                queryset=Device.objects.prefetch_related("capabilities").order_by(
                    "display_name", "serial_number", "id"
                ),
            )
        )
        .order_by("name", "id")
    )

    for g in groups:
        for d in g.devices.all():
            d.is_online_now = bool(d.last_ping and d.last_ping >= threshold)

    # return render(request, "home.html", {"groups": groups})
    return render(request, "home/home.html", {"groups": groups})


@require_POST
@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "你已登出。")
    return redirect("login")


def _parse_group_id(val: str) -> int:
    """支援 'g12' 舊格式；也接受純數字 '12'。"""
    if not val:
        raise Http404("Missing group id")
    if val.startswith("g") and val[1:].isdigit():
        return int(val[1:])
    if val.isdigit():
        return int(val)
    raise Http404("Invalid group id")


@login_required
def ajax_devices(request):
    """
    回傳某群組的裝置 <option>（home/partials/_device_options.html）
    GET /controls/devices/?group_id=g12
    """
    gid_raw = request.GET.get("group_id")
    gid = _parse_group_id(gid_raw)
    group = get_object_or_404(Group, pk=gid)

    # 權限：擁有者或成員（依你 home_view 的寫法）
    is_member = group.users.filter(id=request.user.id).exists()
    if (group.owner_id != request.user.id) and (not is_member):
        return HttpResponseForbidden("No permission")

    # ✅ 補：計算在線狀態
    window = getattr(settings, "DEVICE_ONLINE_WINDOW_SECONDS", 60)
    threshold = timezone.now() - timedelta(seconds=window)

    devices = list(group.devices.select_related("user").all())
    for d in devices:
        d.is_online_now = bool(d.last_ping and d.last_ping >= threshold)

    return render(request, "home/partials/_device_options.html", {"devices": devices})


@login_required
def ajax_caps(request):
    """
    回傳某裝置的能力 <option>（home/partials/_cap_options.html）
    GET /controls/caps/?device_id=34
    """
    did = request.GET.get("device_id")
    if not did:
        raise Http404("Missing device id")

    device = get_object_or_404(Device, pk=did)

    # 權限：該裝置必須屬於使用者可見的群組（擁有者或成員）
    groups_qs = device.groups.all()
    visible = (
        groups_qs.filter(owner=request.user).exists()
        or groups_qs.filter(memberships__user=request.user).exists()
    )
    if not visible:
        return HttpResponseForbidden("No permission")

    # ✅ 不需要匯入 Capability，直接用關聯取
    caps = device.capabilities.filter(enabled=True)
    # caps = device.capabilities.filter(enabled=True).exclude(kind__startswith="sensor")
    return render(request, "home/partials/_cap_options.html", {"caps": caps})


@login_required
def ajax_cap_form(request, cap_id: int):
    device = (
        Device.objects.filter(capabilities__id=cap_id)
        .prefetch_related("groups__memberships", "capabilities")
        .first()
    )
    if not device:
        raise Http404("Capability not found")

    cap = device.capabilities.filter(id=cap_id).first()
    if not cap:
        raise Http404("Capability not found on device")

    gid_raw = request.GET.get("group_id") or request.GET.get("g") or ""
    gid = None
    if gid_raw:
        try:
            gid = int(gid_raw[1:]) if gid_raw.startswith("g") else int(gid_raw)
        except (TypeError, ValueError):
            gid = None

    if gid:
        group = get_object_or_404(Group, pk=gid)
        if not device.groups.filter(pk=group.id).exists():
            return HttpResponseForbidden("Device not in group")
        is_visible = (group.owner_id == request.user.id) or group.memberships.filter(
            user=request.user
        ).exists()
        if not is_visible:
            return HttpResponseForbidden("No permission")
    else:
        visible = device.groups.filter(
            models.Q(owner=request.user) | models.Q(memberships__user=request.user)
        ).exists()
        if not visible:
            return HttpResponseForbidden("No permission")

    # ▼▼ 這裡改成用 proxy URL，避免跨網域/不同 port 問題 ▼▼
    cam_hls_url = request.build_absolute_uri(
        reverse("hls_proxy", args=[device.serial_number, "index.m3u8"])
    )
    # ▲▲

    tpl = {
        "light": "home/forms/_cap_light.html",
        "fan": "home/forms/_cap_fan.html",
        "camera": "home/forms/_cap_camera.html",
        "locker": "home/forms/_cap_locker.html",
    }.get((cap.kind or "").lower(), "home/forms/_cap_generic.html")

    caps_for_select = device.capabilities.filter(enabled=True).exclude(
        kind__startswith="sensor"
    )

    # 為 cap 添加 meta 屬性，包含當前狀態
    cap.meta = cap.cached_state or {}
    
    # 確保 meta 中有必要的狀態欄位
    if not hasattr(cap.meta, 'light_is_on'):
        cap.meta['light_is_on'] = bool(cap.meta.get('light_is_on', False))
    if not hasattr(cap.meta, 'auto_light_running'):
        cap.meta['auto_light_running'] = bool(cap.meta.get('auto_light_running', False))
    if not hasattr(cap.meta, 'locked'):
        cap.meta['locked'] = bool(cap.meta.get('locked', False))

    return render(
        request,
        tpl,
        {
            "cap": cap,
            "device": device,
            "group_id": gid_raw,
            "cam_hls_url": cam_hls_url,
            "caps_for_select": caps_for_select,
        },
    )
