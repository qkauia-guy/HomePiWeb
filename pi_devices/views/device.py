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
from django.db.models import Value, IntegerField, Case, When

import uuid, time
from datetime import timedelta

from ..models import Device, DeviceCommand
from groups.models import GroupDevice
from ..forms import DeviceNameForm, BindDeviceForm

# 🔔 通知服務
from notifications.services import (
    notify_device_bound,
    notify_device_unbound,
    notify_device_renamed,
    notify_group_device_renamed,
    notify_group_device_removed,
    notify_user_online,  # 這個只有 api 會用；留著也無妨
)


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
            return redirect("my_devices")
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
    if device.user_id != request.user.id:
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
    messages.success(request, f"已送出 {action} 指令")
    return redirect(request.META.get("HTTP_REFERER", "my_devices"))


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
