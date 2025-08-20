# pi_devices/views/capability.py
import uuid
from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone

from ..models import Device, DeviceCapability
from ..forms import DeviceCapabilityForm
from ..models import Device, DeviceCapability, DeviceCommand

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


@login_required
@transaction.atomic
def action(request, device_id, cap_id, action):
    device = get_object_or_404(Device, pk=device_id, user=request.user)
    cap = get_object_or_404(DeviceCapability, pk=cap_id, device=device)

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

    cmd = DeviceCommand.objects.create(
        device=device,
        command=cmd_name,
        payload=payload,
        req_id=uuid.uuid4().hex,
        expires_at=timezone.now() + timedelta(minutes=2),
        status="pending",
    )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "req_id": cmd.req_id, "cmd_id": cmd.id})
    messages.success(request, f"已送出 {cmd_name}")
    return redirect(request.META.get("HTTP_REFERER", device.get_absolute_url()))
