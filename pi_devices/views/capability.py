from urllib.parse import urlparse, parse_qs

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Q
from django.urls import reverse

from ..models import Device, DeviceCapability
from ..forms import DeviceCapabilityForm
from groups.models import Group, GroupDevice, GroupMembership

# 佇列工具：沿用 api.py 的一致行為（TTL、欄位）
from .api import _queue_command

from django.middleware.csrf import get_token


# 你原本的常數，保留以供其他能力映射使用
ALLOWED = {
    "light": {"light_on", "light_off", "light_toggle"},
    "fan": {"fan_on", "fan_off", "fan_set_speed"},
}


# ========== CRUD ==========


@login_required
def create(request, device_id):
    device = get_object_or_404(Device, pk=device_id, user=request.user)
    if request.method == "POST":
        form = DeviceCapabilityForm(request.POST)
        if form.is_valid():
            cap = form.save(commit=False)
            cap.device = device
            cap.save()
            messages.success(request, "能力已新增")
            return redirect(device.get_absolute_url())
    else:
        form = DeviceCapabilityForm()
    return render(
        request, "pi_devices/capability_form.html", {"form": form, "device": device}
    )


@login_required
def edit(request, device_id, cap_id):
    device = get_object_or_404(Device, pk=device_id, user=request.user)
    cap = get_object_or_404(DeviceCapability, pk=cap_id, device=device)
    if request.method == "POST":
        form = DeviceCapabilityForm(request.POST, instance=cap)
        if form.is_valid():
            form.save()
            messages.success(request, "能力已更新")
            return redirect(device.get_absolute_url())
    else:
        form = DeviceCapabilityForm(instance=cap)
    return render(
        request,
        "pi_devices/capability_form.html",
        {"form": form, "device": device, "cap": cap},
    )


@login_required
def delete(request, device_id, cap_id):
    device = get_object_or_404(Device, pk=device_id, user=request.user)
    cap = get_object_or_404(DeviceCapability, pk=cap_id, device=device)
    if request.method == "POST":
        cap.delete()
        messages.success(request, "能力已刪除")
        return redirect(device.get_absolute_url())
    return render(
        request,
        "pi_devices/capability_confirm_delete.html",
        {"device": device, "cap": cap},
    )


# ========== helpers ==========


def _parse_gid(val):
    if not val:
        return None
    try:
        if isinstance(val, str) and val.startswith("g"):
            return int(val[1:])
        return int(val)
    except (TypeError, ValueError):
        return None


def _current_group_from_request(request):
    """若你需要從 next=?g=gXX 取群組，可用這個。"""
    gid = (
        request.POST.get("group_id")
        or request.GET.get("group_id")
        or request.POST.get("g")
        or request.GET.get("g")
    )
    gid = _parse_gid(gid)
    if gid:
        return gid
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    try:
        gparam = parse_qs(urlparse(nxt).query).get("g", [None])[0]
        return _parse_gid(gparam)
    except Exception:
        return None


def _can_control(user, group: Group) -> bool:
    """依你現有權限模型調整；目前為：擁有者或成員即可控制。"""
    if group.owner_id == user.id:
        return True
    return group.memberships.filter(user=user).exists()


def _resolve_group(request, device: Device):
    """
    從表單/URL 解析 group，並做包含性與權限檢查。
    回傳：(group | None, error_message | None, raw_gid_str)
    """
    gid_raw = (
        request.POST.get("group_id")
        or request.GET.get("group_id")
        or request.POST.get("g")
        or request.GET.get("g")
        or ""
    )
    gid = None
    if gid_raw:
        try:
            gid = int(gid_raw[1:]) if str(gid_raw).startswith("g") else int(gid_raw)
        except Exception:
            gid = None

    if gid:
        group = get_object_or_404(Group, pk=gid)
        if not GroupDevice.objects.filter(group=group, device=device).exists():
            return None, "Device not in group", gid_raw
        if not _can_control(request.user, group):
            return None, "No permission", gid_raw
        return group, None, gid_raw

    group = (
        Group.objects.filter(devices=device)
        .filter(Q(owner=request.user) | Q(memberships__user=request.user))
        .distinct()
        .first()
    )
    if not group or not _can_control(request.user, group):
        return None, "No permission", gid_raw
    return group, None, f"g{group.id}"


# ========== Actions ==========


@login_required
@require_POST
def action(request, device_id: int, cap_id: int, action: str):
    """
    傳統 action 入口：/devices/<device_id>/cap/<cap_id>/action/<action>/
    - light: on/off/toggle
    - camera: start/stop/status
    這裡改為使用 _queue_command()；其餘導回行為維持不變。
    """
    device = get_object_or_404(Device, pk=device_id)
    cap = get_object_or_404(DeviceCapability, pk=cap_id, device=device)

    # 權限與群組解析
    group, err, gid_raw = _resolve_group(request, device)
    if err:
        return HttpResponseForbidden(err)

    kind = (cap.kind or "").lower()
    if kind == "light":
        mapping = {"on": "light_on", "off": "light_off", "toggle": "light_toggle"}
    elif kind in ("camera", "cam"):
        mapping = {
            "start": "camera_start",
            "stop": "camera_stop",
            "status": "camera_status",
        }
    else:
        mapping = {}

    cmd_name = mapping.get((action or "").lower())
    if cmd_name:
        payload = {"slug": cap.slug} if getattr(cap, "slug", None) else {}
        _queue_command(device, cmd_name, payload=payload)

    next_url = request.POST.get("next")
    if not next_url:
        next_url = reverse("home") + f"?g={gid_raw}&d={device.id}&cap={cap.id}"
    return redirect(next_url)


@login_required
@require_POST
def capability_action(request, device_id: int, cap_id: int, action: str):
    """
    你的模板正在使用的入口：
    /devices/<device_id>/caps/<int:cap_id>/<str:action>/

    修正點：
    - camera 類型會佇列 camera_start / camera_stop，payload 帶 cap.slug（若有）
    - 其餘能力照舊（light 映射 on/off/toggle；未支援的安全導回）
    """
    device = get_object_or_404(Device, pk=device_id)
    cap = get_object_or_404(DeviceCapability, pk=cap_id, device=device)

    # ===== 權限檢查（維持你原本邏輯）=====
    gid_raw = request.POST.get("group_id") or request.GET.get("group_id") or ""
    gid = _parse_gid(gid_raw)

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
            Q(owner=request.user) | Q(memberships__user=request.user)
        ).exists()
        if not visible:
            return HttpResponseForbidden("No permission")

    # ===== 動作對映 =====
    kind = (cap.kind or "").strip().lower()
    act = (action or "").strip().lower()

    cmd_name = None
    if kind == "light":
        cmd_name = {"on": "light_on", "off": "light_off", "toggle": "light_toggle"}.get(
            act
        )
    elif "camera" in kind or kind == "cam":
        base = {
            "start": "camera_start",
            "stop": "camera_stop",
            "status": "camera_status",
        }
        cmd_name = base.get(act)

    if cmd_name:
        payload = {"slug": cap.slug} if getattr(cap, "slug", None) else {}
        _queue_command(device, cmd_name, payload=payload)
        # 可選：messages.success(request, f"已送出 {cap.name}：{cmd_name}")
    # 未支援 → 安全導回（不噴 400）

    # ===== 導回原頁（維持 g/d/cap）=====
    next_url = request.POST.get("next") or request.GET.get("next")
    if not next_url:
        params = []
        if gid_raw:
            params.append(f"g={gid_raw}")
        params += [f"d={device.id}", f"cap={cap.id}"]
        next_url = reverse("home") + "?" + "&".join(params)
    return redirect(next_url)


@login_required
def live_player(request, device_id: int, cap_id: int):
    device = get_object_or_404(Device, pk=device_id)
    cap = get_object_or_404(DeviceCapability, pk=cap_id, device=device)

    # 權限：裝置需在使用者可見群組
    gid_raw = request.GET.get("group_id") or request.GET.get("g") or ""
    gid = _parse_gid(gid_raw)
    if gid:
        group = get_object_or_404(Group, pk=gid)
        in_group = device.groups.filter(pk=group.id).exists()
        visible = (group.owner_id == request.user.id) or group.memberships.filter(
            user=request.user
        ).exists()
        if not in_group or not visible:
            return HttpResponseForbidden("No permission")
    else:
        visible = device.groups.filter(
            Q(owner=request.user) | Q(memberships__user=request.user)
        ).exists()
        if not visible:
            return HttpResponseForbidden("No permission")

    cam_hls_url = request.build_absolute_uri(
        reverse("hls_proxy", args=[device.serial_number, "index.m3u8"])
    )
    ctx = {
        "device": device,
        "cap": cap,
        "group_id": gid_raw,
        "cam_hls_url": cam_hls_url,
        "csrf_token": get_token(request),
        "start_url": reverse("capability_action", args=[device.id, cap.id, "start"]),
        "stop_url": reverse("capability_action", args=[device.id, cap.id, "stop"]),
    }
    return render(request, "pi_devices/live_player.html", ctx)
