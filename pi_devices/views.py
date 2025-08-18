# pi_devices/views.py
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.db import transaction

import json
from datetime import timedelta  # ← 用這個，不要 timezone.timedelta
from django.conf import settings

from .models import Device
from groups.models import GroupDevice
from .forms import DeviceNameForm, BindDeviceForm

# 🔔 通知服務
from notifications.services import (
    notify_device_bound,
    notify_device_unbound,
    notify_device_renamed,
    notify_device_ip_changed,
    notify_group_device_renamed,
    notify_group_device_removed,
    notify_user_online,
)


@login_required
def my_devices(request):
    devices = request.user.devices.all().order_by("-created_at")
    return render(request, "pi_devices/my_devices.html", {"devices": devices})


@login_required
@transaction.atomic
def device_edit_name(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if device.user_id != request.user.id:
        return HttpResponseForbidden("你沒有權限編輯這台裝置。")

    # 舊顯示名（支援 name 屬性或 name() 方法）
    old_name_display = (
        device.name()
        if callable(getattr(device, "name", None))
        else getattr(device, "name", "")
    )

    if request.method == "POST":
        form = DeviceNameForm(request.POST, instance=device)
        if form.is_valid():
            changed = set(form.changed_data)
            form.save()  # 已寫入新名稱

            new_name_display = (
                device.name()
                if callable(getattr(device, "name", None))
                else getattr(device, "name", "")
            )

            # 若名稱確實變更才處理通知與快取同步
            if (old_name_display != new_name_display) and (
                {"name", "display_name", "label"} & changed
            ):
                # 1) 同步 GroupDevice 的名稱快取（若 through 有這欄位）
                try:
                    if any(
                        getattr(f, "name", None) == "device_name_cache"
                        for f in GroupDevice._meta.get_fields()
                    ):
                        GroupDevice.objects.filter(device=device).update(
                            device_name_cache=new_name_display or ""
                        )
                except Exception:
                    # 沒這欄位就跳過，不影響主要流程
                    pass

                # 2) 交易提交後才發通知：擁有者 + 群組廣播
                def _after_commit():
                    # 擁有者通知
                    notify_device_renamed(
                        device=device,
                        owner=request.user,
                        old_name=old_name_display or "",
                        new_name=new_name_display or "",
                        actor=request.user,
                    )
                    # 群組廣播
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
        request, "pi_devices/device_edit_name.html", {"form": form, "device": device}
    )


@login_required
@require_http_methods(["GET", "POST"])
def device_bind(request):
    if request.method == "POST":
        form = BindDeviceForm(request.POST)
        if form.is_valid():
            device = form.cleaned_data["device"]
            with transaction.atomic():
                # 再鎖一次，避免競態
                device = Device.objects.select_for_update().get(pk=device.pk)
                if device.is_bound or device.user_id is not None:
                    messages.error(
                        request, "此設備剛剛已被綁定，請再確認序號與驗證碼。"
                    )
                    return redirect("my_devices")

                device.user = request.user
                device.is_bound = True
                device.save(update_fields=["user", "is_bound"])

                # ✅ 交易提交後才送通知
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
@login_required
@require_http_methods(["GET", "POST"])
def device_unbind(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if device.user_id != request.user.id:
        return HttpResponseForbidden("你沒有權限操作此裝置。")

    # ---- GET：顯示確認頁並附上群組清單 ----
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

    # ---- POST：解除綁定 + 自所有群組移除 + 發通知 ----
    with transaction.atomic():
        locked = Device.objects.select_for_update().get(pk=device.pk)
        owner_before = request.user

        # 先抓出所有關聯群組（用於後續通知與訊息）
        gds = list(GroupDevice.objects.select_related("group").filter(device=locked))
        related_groups = [gd.group for gd in gds]

        # 刪除裝置在所有群組的關聯
        GroupDevice.objects.filter(device=locked).delete()

        # 解除綁定
        locked.user = None
        locked.is_bound = False
        locked.save(update_fields=["user", "is_bound"])

        # 交易提交後才送通知
        def _after_commit():
            notify_device_unbound(device=locked, owner=owner_before, actor=request.user)
            for grp in related_groups:
                notify_group_device_removed(
                    actor=request.user, group=grp, device=locked
                )

        transaction.on_commit(_after_commit)

    messages.success(request, f"已解除綁定，並自 {len(related_groups)} 個群組移除。")
    return redirect("my_devices")


@csrf_exempt
@require_POST
def device_ping(request):
    """
    由裝置端呼叫：
      - 驗證 serial_number + token
      - 更新 last_ping / ip_address
      - 若 IP 有變更，通知擁有者（每天同一 IP 只發一次，邏輯在 services 內處理）
      - 若「離線 → 上線」，通知該使用者所在群組的其他人（每天一則/人/群組）
    """
    # 1) 解析 JSON
    body = request.body.decode("utf-8") if request.body else ""
    if not body:
        return JsonResponse({"error": "Empty body"}, status=400)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    serial = data.get("serial_number")
    token = data.get("token")  # 強制驗證
    if not serial:
        return JsonResponse({"error": "No serial_number"}, status=400)
    if not token:
        return JsonResponse({"error": "No token"}, status=401)

    # 2) 來源 IP（若有反代才信任 XFF）
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    client_ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")

    # 3) 讀取並比對，必要時送出通知
    try:
        with transaction.atomic():
            device = (
                Device.objects.select_for_update()
                .only(
                    "id", "serial_number", "token", "ip_address", "user_id", "last_ping"
                )
                .get(serial_number=serial)
            )
            if device.token != token:
                return JsonResponse({"error": "Unauthorized"}, status=401)

            owner_id = device.user_id
            now = timezone.now()
            window = getattr(settings, "DEVICE_ONLINE_WINDOW_SECONDS", 60)
            threshold = now - timedelta(seconds=window)  # ← 用 datetime.timedelta

            # ---------- 判斷「之前是否在線」（更新前的狀態） ----------
            was_online = False
            if owner_id:
                # 這台裝置是否在視窗內
                was_online = bool(device.last_ping and device.last_ping >= threshold)
                if not was_online:
                    # 同使用者其他裝置是否在線
                    was_online = (
                        Device.objects.filter(
                            user_id=owner_id, last_ping__gte=threshold
                        )
                        .exclude(pk=device.pk)
                        .exists()
                    )

            old_ip = device.ip_address or None
            ip_changed = old_ip != client_ip

            # ---------- 寫入最新心跳/IP ----------
            device.last_ping = now
            device.ip_address = client_ip
            device.save(update_fields=["last_ping", "ip_address"])

            # ---------- 上線通知：只在「離線 → 上線」且有擁有者時 ----------
            if owner_id and not was_online:
                from django.contrib.auth import get_user_model

                User = get_user_model()
                subject_user = User.objects.filter(pk=owner_id).first()
                if subject_user:
                    transaction.on_commit(lambda: notify_user_online(user=subject_user))

            # ---------- IP 變更通知 ----------
            if ip_changed and owner_id:
                # 若擔心 lazy relation，可改成再次查詢 User；通常直接用也可
                transaction.on_commit(
                    lambda: notify_device_ip_changed(
                        device=device,
                        owner=device.user,
                        old_ip=old_ip,
                        new_ip=client_ip,
                    )
                )

    except Device.DoesNotExist:
        return JsonResponse({"error": "Device not found"}, status=404)

    return JsonResponse({"status": "pong", "ip": client_ip})
