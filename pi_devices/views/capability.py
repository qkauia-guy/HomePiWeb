# pi_devices/views/capability.py
import uuid
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone

from ..models import Device, DeviceCapability
from ..forms import DeviceCapabilityForm
from ..models import Device, DeviceCapability, DeviceCommand
from groups.models import Group, GroupDevice, GroupMembership
from groups.models import GroupMembership, GroupDevicePermission

ALLOWED = {
    "light": {"light_on", "light_off", "light_toggle"},
    "fan": {"fan_on", "fan_off", "fan_set_speed"},
}


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


# ===== helpers =====
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
    # 先看顯式參數（POST/GET: group_id 或 g）
    gid = (
        request.POST.get("group_id")
        or request.GET.get("group_id")
        or request.POST.get("g")
        or request.GET.get("g")
    )
    gid = _parse_gid(gid)
    if gid:
        return gid
    # 再從 next 的查詢參數撈 ?g=gXX
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    try:
        gparam = parse_qs(urlparse(nxt).query).get("g", [None])[0]
        return _parse_gid(gparam)
    except Exception:
        return None


def _user_can_control(user, group, device):
    if group.owner_id == user.id:
        return True
    role = (
        GroupMembership.objects.filter(group=group, user=user)
        .values_list("role", flat=True)
        .first()
    )
    if role == "admin":
        return True
    if role == "operator":
        return GroupDevicePermission.objects.filter(
            user=user, group=group, device=device, can_control=True
        ).exists()
    return False


# 你原本的 ALLOWED 常數請保留
# ALLOWED = {"light": {"light_on", "light_off", "light_toggle"}, "fan": {...}}


@login_required
@require_POST
def action(request, device_id, cap_id, action):
    # 1) 只用 pk 取裝置（不要 user=request.user，避免非擁有者變 404）
    device = get_object_or_404(Device, pk=device_id)

    # 2) 確認該能力屬於此裝置
    cap = get_object_or_404(DeviceCapability, pk=cap_id, device=device)

    # 3) 找出此次操作所屬的群組
    gid = _current_group_from_request(request)
    if gid:
        group = get_object_or_404(Group, pk=gid)
        # 裝置必須在該群組內
        if not GroupDevice.objects.filter(group=group, device=device).exists():
            return HttpResponseForbidden("Device not in group")
    else:
        # 沒帶群組 → 從「裝置所在群組 ∩ 我可見的群組」挑一個
        group = (
            Group.objects.filter(devices=device)
            .filter(Q(owner=request.user) | Q(memberships__user=request.user))
            .distinct()
            .first()
        )
        if not group:
            return HttpResponseForbidden("No permission")

    # 4) 角色權限：owner/admin/operator 才能操作；viewer 禁止
    if not _user_can_control(request.user, group, device):
        return HttpResponseForbidden("No permission")

    # 5) 動作映射與檢核（保留你的原邏輯）
    semantic = {
        "on": {"light": "light_on", "fan": "fan_on"},
        "off": {"light": "light_off", "fan": "fan_off"},
        "toggle": {"light": "light_toggle"},
        "set_speed": {"fan": "fan_set_speed"},
    }
    cmd_name = semantic.get(action, {}).get(cap.kind) or action
    if cmd_name not in ALLOWED.get(cap.kind, set()):
        return JsonResponse({"error": "invalid action for capability"}, status=400)

    payload = {"cap_slug": cap.slug, "config": cap.config}
    if cmd_name == "fan_set_speed":
        try:
            speed = int(request.POST.get("speed", ""))
        except ValueError:
            return JsonResponse({"error": "speed must be integer"}, status=400)
        max_level = int(cap.config.get("levels", 5))
        if not 1 <= speed <= max_level:
            return JsonResponse({"error": f"speed must be 1~{max_level}"}, status=400)
        payload["speed"] = speed

    # 6) 建立指令（不包 transaction.atomic，減少 sqlite 鎖風險）
    cmd = DeviceCommand.objects.create(
        device=device,
        command=cmd_name,
        payload=payload,
        req_id=uuid.uuid4().hex,
        expires_at=timezone.now() + timedelta(minutes=2),
        status="pending",
    )

    # 7) 回應
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "req_id": cmd.req_id, "cmd_id": cmd.id})
    # 非 XHR：回上一頁
    from django.contrib import messages

    messages.success(request, f"已送出 {cmd_name}")
    return redirect(request.META.get("HTTP_REFERER", device.get_absolute_url()))


@login_required
@require_POST
def capability_action(request, device_id, cap_id, action):
    # 1) 只用 pk 取裝置；不要限制 user=request.user
    device = get_object_or_404(Device, pk=device_id)

    # 2) 確認該能力屬於此裝置（避免亂打）
    cap = device.capabilities.filter(pk=cap_id).first()
    if not cap:
        raise Http404("Capability not found on device")

    # 3) 找到操作所屬的群組（前端表單傳 group_id；若沒傳，就從「此裝置所在群組 ∩ 我可見的群組」挑一個）
    gid_raw = (
        request.POST.get("group_id")
        or request.GET.get("group_id")
        or request.POST.get("g")
        or request.GET.get("g")
    )
    group = None
    if gid_raw:
        gid = (
            int(gid_raw[1:])
            if isinstance(gid_raw, str) and gid_raw.startswith("g")
            else int(gid_raw)
        )
        group = get_object_or_404(Group, pk=gid)
        # 裝置必須在該群組
        if not GroupDevice.objects.filter(group=group, device=device).exists():
            return HttpResponseForbidden("Device not in group")
        # 檢查角色權限（owner/admin/operator 才能操作）
        if not can_control_device(request.user, group):
            return HttpResponseForbidden("No permission")
    else:
        # 沒帶 group_id：從裝置所在群組挑一個我有權限的
        qs = (
            Group.objects.filter(devices=device)
            .filter(Q(owner=request.user) | Q(memberships__user=request.user))
            .distinct()
        )
        if not qs.exists():
            return HttpResponseForbidden("No permission")
        # 這裡挑第一個；或你可以用你的 URL 狀態（?g=g12）去精準匹配
        group = qs.first()
        if not can_control_device(request.user, group):
            return HttpResponseForbidden("No permission")

    # 4) 到這裡才執行實際指令（你原本的下發邏輯）
    # 例如：enqueue_command(device, cap, action, payload=request.POST.dict())
    # ……(略)

    return JsonResponse(
        {"ok": True, "device": device.id, "cap": cap.id, "action": action}
    )
