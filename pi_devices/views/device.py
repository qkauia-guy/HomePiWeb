# pi_devices/views/device.py
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.db import transaction
from django.conf import settings
from django.db.models.functions import Coalesce, NullIf
from django.db.models import Value, IntegerField, Case, When, Q
from groups.permissions import can_control_device as _can_control_device
import uuid, time
from datetime import timedelta
import datetime

from ..models import Device, DeviceCapability, DeviceSchedule
from ..forms import DeviceNameForm, BindDeviceForm
from groups.models import Group, GroupMembership, GroupDevicePermission, GroupDevice
from django.utils.dateparse import parse_datetime
from datetime import timezone as dt_timezone
from django.views.decorators.cache import never_cache


# 🔔 通知服務
from notifications.services import (
    notify_device_bound,
    notify_device_unbound,
    notify_device_renamed,
    notify_group_device_renamed,
    notify_group_device_removed,
    notify_user_online,  # 這個只有 api 會用；留著也無妨
)


# =========================
# ✅ 新增：工具與權限判斷
# =========================
def _parse_group_id(val: str | None) -> int | None:
    if not val:
        return None
    s = val.strip()
    if s.startswith("g") and s[1:].isdigit():
        return int(s[1:])
    if s.isdigit():
        return int(s)
    return None


def _user_can_control(user, device: Device, group: Group | None) -> bool:
    """
    權限規則：
      - 裝置擁有者：可控
      - 群組擁有者 / 群組 admin：可控
      - operator：需要在 GroupDevicePermission 有 can_control=True
      - viewer：不可控
    若 group 為 None，會嘗試使用者可見的任一包含該裝置的群組來判斷。
    """
    # 裝置擁有者
    if device.user_id == user.id:
        return True

    def _check_one_group(g: Group) -> bool:
        if g.owner_id == user.id:
            return True
        ms = GroupMembership.objects.filter(group=g, user=user).only("role").first()
        if not ms:
            return False
        if ms.role == "admin":
            return True
        if ms.role == "operator":
            return GroupDevicePermission.objects.filter(
                user=user, group=g, device=device, can_control=True
            ).exists()
        return False  # viewer

    if group:
        # 要求裝置確實存在該群組
        if not GroupDevice.objects.filter(group=group, device=device).exists():
            return False
        return _check_one_group(group)

    # 未指定群組：用使用者可見的群組（且群組包含該裝置）嘗試判斷
    gs = (
        Group.objects.filter(devices=device)
        .filter(Q(owner=user) | Q(memberships__user=user))
        .distinct()
    )
    for g in gs:
        if _check_one_group(g):
            return True
    return False


@login_required
def offcanvas_list(request):
    threshold = timezone.now() - timedelta(seconds=60)
    devices = (
        Device.objects.filter(user=request.user)
        .annotate(
            sort_name=Coalesce(NullIf("display_name", Value("")), "serial_number")
        )
        .annotate(
            online_int=Case(
                When(last_ping__gte=threshold, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("-online_int", "sort_name", "id")
    )
    return render(request, "pi_devices/_offcanvas_devices.html", {"devices": devices})


@login_required
def my_devices(request):
    devices = request.user.devices.all().order_by("-created_at")
    return render(request, "pi_devices/my_devices.html", {"devices": devices})


@login_required
@transaction.atomic
def device_edit(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if device.user_id != request.user.id:
        return HttpResponseForbidden("你沒有權限編輯這台裝置。")

    old_name_display = (
        device.name()
        if callable(getattr(device, "name", None))
        else getattr(device, "name", "")
    )
    if request.method == "POST":
        form = DeviceNameForm(request.POST, instance=device)
        if form.is_valid():
            changed = set(form.changed_data)
            form.save()
            new_name_display = (
                device.name()
                if callable(getattr(device, "name", None))
                else getattr(device, "name", "")
            )
            if (old_name_display != new_name_display) and (
                {"name", "display_name", "label"} & changed
            ):
                try:
                    if any(
                        getattr(f, "name", None) == "device_name_cache"
                        for f in GroupDevice._meta.get_fields()
                    ):
                        GroupDevice.objects.filter(device=device).update(
                            device_name_cache=new_name_display or ""
                        )
                except Exception:
                    pass

                def _after_commit():
                    notify_device_renamed(
                        device=device,
                        owner=request.user,
                        old_name=old_name_display or "",
                        new_name=new_name_display or "",
                        actor=request.user,
                    )
                    for gd in GroupDevice.objects.filter(device=device).select_related(
                        "group"
                    ):
                        notify_group_device_renamed(
                            actor=request.user,
                            group=gd.group,
                            device=device,
                            old_name=old_name_display or "",
                            new_name=new_name_display or "",
                        )

                transaction.on_commit(_after_commit)
            messages.success(request, "已更新裝置名稱。")
            return redirect("home")
    else:
        form = DeviceNameForm(instance=device)
    return render(
        request, "pi_devices/device_edit.html", {"form": form, "device": device}
    )


@login_required
@require_http_methods(["GET", "POST"])
def device_bind(request):
    if request.method == "POST":
        form = BindDeviceForm(request.POST)
        if form.is_valid():
            device = form.cleaned_data["device"]
            with transaction.atomic():
                device = Device.objects.select_for_update().get(pk=device.pk)
                if device.is_bound or device.user_id is not None:
                    messages.error(
                        request, "此設備剛剛已被綁定，請再確認序號與驗證碼。"
                    )
                    return redirect("my_devices")
                device.user = request.user
                device.is_bound = True
                device.save(update_fields=["user", "is_bound"])
                transaction.on_commit(
                    lambda: notify_device_bound(
                        device=device, owner=request.user, actor=request.user
                    )
                )
            messages.success(request, f"綁定成功！({device.serial_number})")
            return redirect("my_devices")
    else:
        initial = {}
        if request.GET.get("serial"):
            initial["serial_number"] = request.GET["serial"].strip()
        if request.GET.get("code"):
            initial["verification_code"] = request.GET["code"].strip()
        form = BindDeviceForm(initial=initial)
    return render(request, "pi_devices/device_bind.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def device_unbind(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if device.user_id != request.user.id:
        return HttpResponseForbidden("你沒有權限操作此裝置。")

    if request.method == "GET":
        group_devices = (
            GroupDevice.objects.select_related("group")
            .filter(device=device)
            .order_by("group__name")
        )
        return render(
            request,
            "pi_devices/device_unbind_confirm.html",
            {"device": device, "group_devices": group_devices},
        )

    with transaction.atomic():
        locked = Device.objects.select_for_update().get(pk=device.pk)
        owner_before = request.user
        gds = list(GroupDevice.objects.select_related("group").filter(device=locked))
        related_groups = [gd.group for gd in gds]
        GroupDevice.objects.filter(device=locked).delete()
        locked.user = None
        locked.is_bound = False
        locked.save(update_fields=["user", "is_bound"])

        def _after_commit():
            notify_device_unbound(device=locked, owner=owner_before, actor=request.user)
            for grp in related_groups:
                notify_group_device_removed(
                    actor=request.user, group=grp, device=locked
                )

        transaction.on_commit(_after_commit)

    messages.success(request, f"已解除綁定，並自 {len(related_groups)} 個群組移除。")
    return redirect("home")


# === 使用者下指令：建立 pending 指令（舊：只控制燈） ===
@login_required
@require_POST
def device_light_action(request, device_id, action):
    if action not in ("on", "off", "toggle"):
        return JsonResponse({"error": "invalid action"}, status=400)

    device = get_object_or_404(Device, pk=device_id)

    # 解析群組：POST hidden group_id > GET ?g
    gid = (
        _parse_group_id(request.POST.get("group_id"))
        or _parse_group_id(request.GET.get("g"))
        or _parse_group_id(request.GET.get("group_id"))
    )
    group = get_object_or_404(Group, pk=gid) if gid else None

    if not _can_control_device(request.user, device, group):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"error": "forbidden"}, status=403)
        return HttpResponseForbidden("你沒有權限操作此裝置。")

    cmd_map = {"on": "light_on", "off": "light_off", "toggle": "light_toggle"}
    cmd_name = cmd_map[action]

    cmd = DeviceCommand.objects.create(
        device=device,
        command=cmd_name,
        payload={},
        req_id=uuid.uuid4().hex,
        expires_at=timezone.now() + timedelta(minutes=2),
        status="pending",
    )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {"ok": True, "req_id": cmd.req_id, "cmd_id": cmd.id}, status=200
        )

    next_url = request.POST.get("next") or request.META.get(
        "HTTP_REFERER", "my_devices"
    )
    messages.success(request, f"已送出 {action} 指令")
    return redirect(next_url)


# === 範例：解鎖（若你還要保留） ===
@login_required
@require_POST
def unlock_device(request, device_id: int):
    device = get_object_or_404(Device, pk=device_id)
    if device.user_id != request.user.id:
        return HttpResponseForbidden("你沒有權限控制此裝置。")
    req_id = uuid.uuid4().hex
    expires = timezone.now() + timedelta(
        seconds=getattr(settings, "DEVICE_COMMAND_EXPIRES_SECONDS", 30)
    )
    DeviceCommand.objects.create(
        device=device,
        command="unlock",
        payload={},
        req_id=req_id,
        expires_at=expires,
        status="pending",
    )
    return JsonResponse({"ok": True, "req_id": req_id})


def _make_aware_to_utc(dt: datetime.datetime | None) -> datetime.datetime | None:
    """接受 naive 或 aware 的 datetime；回傳 UTC-aware；不是 datetime 就回 None。"""
    if not isinstance(dt, datetime.datetime):
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt.astimezone(datetime.timezone.utc)


@login_required
@require_POST
def create_schedule(request):
    """
    單一表單即可：
      必填：device_id, slug(可選，但建議帶)
      可填：on_at_local / on_at_iso、off_at_local / off_at_iso（擇一或兩者都填）
      其他可選 payload：sensor / led / target / name / slug
    相容舊版：
      run_at_iso / run_at_local + action（若你還有舊按鈕）
    """
    device_id = request.POST.get("device_id")
    if not device_id:
        return JsonResponse({"ok": False, "error": "missing device_id"}, status=400)

    device = get_object_or_404(Device, pk=device_id)

    # 權限：裝置需在使用者可見群組
    visible = device.groups.filter(
        Q(owner=request.user) | Q(memberships__user=request.user)
    ).exists()
    if not visible:
        return JsonResponse({"ok": False, "error": "no permission"}, status=403)

    # ---- 解析新的兩組時間欄位 ----
    on_at_iso = (request.POST.get("on_at_iso") or "").strip() or None
    off_at_iso = (request.POST.get("off_at_iso") or "").strip() or None
    on_at_local = (request.POST.get("on_at_local") or "").strip() or None
    off_at_local = (request.POST.get("off_at_local") or "").strip() or None

    # 相容舊欄位（若只給 run_at_* + action）
    legacy_action = (request.POST.get("action") or "").strip() or None
    legacy_run_iso = (request.POST.get("run_at_iso") or "").strip() or None
    legacy_run_local = (request.POST.get("run_at_local") or "").strip() or None

    def _parse_to_utc(text: str | None):
        if not text:
            return None
        dt = parse_datetime(text)
        if not dt:
            return None
        return _make_aware_to_utc(dt)

    # 新版：各自解析
    on_dt_utc = _parse_to_utc(on_at_iso) or _parse_to_utc(on_at_local)
    off_dt_utc = _parse_to_utc(off_at_iso) or _parse_to_utc(off_at_local)

    # 舊版：若新欄位都沒填，才啟用舊參數
    legacy_dt_utc = None
    if (
        not on_dt_utc
        and not off_dt_utc
        and (legacy_action and (legacy_run_iso or legacy_run_local))
    ):
        legacy_dt_utc = _parse_to_utc(legacy_run_iso) or _parse_to_utc(legacy_run_local)
        if not legacy_dt_utc:
            return JsonResponse({"ok": False, "error": "bad datetime"}, status=400)

    # 至少要有一個有效時間
    if not on_dt_utc and not off_dt_utc and not legacy_dt_utc:
        return JsonResponse(
            {"ok": False, "error": "no schedule time provided"}, status=400
        )

    # 打包 payload（讓 agent 能帶回狀態）
    payload = {}
    for k in ("sensor", "led", "slug", "target", "name"):
        v = request.POST.get(k)
        if v:
            payload[k] = v

    created = []

    # 新版：自動判斷建立哪種排程
    now = timezone.now()
    if on_dt_utc:
        if on_dt_utc < now:
            return JsonResponse(
                {"ok": False, "error": "on time is in the past"}, status=400
            )
        s = DeviceSchedule.objects.create(
            device=device, action="light_on", payload=payload, run_at=on_dt_utc
        )
        created.append(
            {"id": s.id, "action": s.action, "run_at": int(s.run_at.timestamp())}
        )

    if off_dt_utc:
        if off_dt_utc < now:
            return JsonResponse(
                {"ok": False, "error": "off time is in the past"}, status=400
            )
        s = DeviceSchedule.objects.create(
            device=device, action="light_off", payload=payload, run_at=off_dt_utc
        )
        created.append(
            {"id": s.id, "action": s.action, "run_at": int(s.run_at.timestamp())}
        )

    # 舊版：只有在新欄位沒填時才使用
    if legacy_dt_utc:
        if legacy_action not in (
            "light_on",
            "light_off",
            "auto_light_on",
            "auto_light_off",
        ):
            return JsonResponse({"ok": False, "error": "bad legacy action"}, status=400)
        if legacy_dt_utc < now:
            return JsonResponse(
                {"ok": False, "error": "legacy time is in the past"}, status=400
            )
        s = DeviceSchedule.objects.create(
            device=device, action=legacy_action, payload=payload, run_at=legacy_dt_utc
        )
        created.append(
            {"id": s.id, "action": s.action, "run_at": int(s.run_at.timestamp())}
        )

    return JsonResponse({"ok": True, "created": created})


@never_cache
@login_required
def upcoming_schedules(request, device_id: int):
    """
    回傳此裝置（可選 slug）即將到來的開/關排程（僅 pending）
    GET params:
      - slug: 限定某個 capability（例如 light 的 slug）
    """
    from ..models import Device, DeviceSchedule  # 避免上方循環 import

    device = get_object_or_404(Device, pk=device_id)

    # 權限簡查：裝置必須在使用者可見群組
    visible = device.groups.filter(
        Q(owner=request.user) | Q(memberships__user=request.user)
    ).exists()
    if not visible:
        return JsonResponse({"ok": False, "error": "no permission"}, status=403)

    slug = (request.GET.get("slug") or "").strip()

    # 容忍裝置/瀏覽器時鐘些微誤差
    DRIFT_SEC = 120
    now = timezone.now()

    qs = (
        DeviceSchedule.objects.filter(
            device=device,
            status="pending",
            run_at__gte=now - timedelta(seconds=DRIFT_SEC),
        )
        .filter(action__in=["light_on", "light_off"])
        .order_by("run_at")
    )
    if slug:
        qs = qs.filter(payload__slug=slug)

    # 找出下一次 on/off（已依 run_at 排序）
    next_on = qs.filter(action="light_on").first()
    next_off = qs.filter(action="light_off").first()

    # 若時間已經過去（再給一點很小的緩衝 5 秒），視為無效 → 回傳 None
    def sanitize_next(s):
        if not s:
            return None
        # 5 秒的超短緩衝，避免 race 導致剛過點就被清掉
        if s.run_at <= now - timedelta(seconds=5):
            return None
        return s

    next_on = sanitize_next(next_on)
    next_off = sanitize_next(next_off)

    def pack(s):
        if not s:
            return None
        return {
            "id": s.id,
            "action": s.action,
            "ts": int(s.run_at.timestamp()),
            "iso": s.run_at.isoformat(),
            "payload": s.payload or {},
        }

    items = [
        {
            "id": s.id,
            "action": s.action,
            "ts": int(s.run_at.timestamp()),
            "iso": s.run_at.isoformat(),
            "payload": s.payload or {},
        }
        for s in qs[:50]
    ]

    resp = JsonResponse(
        {
            "ok": True,
            "server_ts": int(now.timestamp()),
            "next_on": pack(next_on),
            "next_off": pack(next_off),
            "items": items,
        }
    )
    resp["Cache-Control"] = "no-store"
    return resp
