# pi_devices/views.py
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.db import transaction
from django.conf import settings

import json
from datetime import timedelta

from .models import Device, DeviceCommand
from groups.models import GroupDevice
from .forms import DeviceNameForm, BindDeviceForm
import uuid, time
from django.db.models.functions import Coalesce, NullIf
from django.db.models import Value, IntegerField, Case, When


@login_required
def offcanvas_list(request):
    # 與你的 is_online(window_seconds=60) 一致
    threshold = timezone.now() - timedelta(seconds=60)

    devices = (
        Device.objects.filter(user=request.user)
        # 排序/顯示名稱：display_name（若為空/None就退回 serial_number）
        .annotate(
            sort_name=Coalesce(NullIf("display_name", Value("")), "serial_number")
        )
        # 註記一個可排序的「是否在線」欄位（1/0）
        .annotate(
            online_int=Case(
                When(last_ping__gte=threshold, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        # ★ 用 online_int 排序，不要用 is_online
        .order_by("-online_int", "sort_name", "id")
    )

    return render(request, "pi_devices/_offcanvas_devices.html", {"devices": devices})


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
    return redirect("home")


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


# === 使用者下指令：建立一筆 pending 指令 ===
@login_required
@require_POST
def unlock_device(request, device_id: int):
    device = get_object_or_404(Device, pk=device_id)
    # 最小 MVP 權限：必須是擁有者（之後再擴充群組規則）
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


# === 裝置長輪詢：領取最舊的 pending 指令 ===
@csrf_exempt
@require_POST
def device_pull(request):
    """
    輸入：
      { "serial_number": "...", "token": "...", "max_wait": 20 }
    回傳：
      取得指令 → {"cmd":"unlock","req_id":"...","payload":{...}}
      無指令 → 204 No Content（或 {"cmd": null}）
    """
    # 解析/驗證
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    serial = data.get("serial_number")
    token = data.get("token")
    max_wait = int(
        data.get("max_wait") or getattr(settings, "DEVICE_COMMAND_MAX_WAIT_SECONDS", 20)
    )
    if not serial or not token:
        return JsonResponse({"error": "serial_number/token required"}, status=400)

    try:
        device = Device.objects.only("id", "serial_number", "token").get(
            serial_number=serial
        )
    except Device.DoesNotExist:
        return JsonResponse({"error": "Device not found"}, status=404)

    if device.token != token:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    # 長輪詢：每 200ms 嘗試撈一次，直到超時
    deadline = time.time() + max_wait
    while True:
        with transaction.atomic():
            # 過期的 pending 先標 expired（保險）
            now = timezone.now()
            DeviceCommand.objects.filter(
                device=device, status="pending", expires_at__lte=now
            ).update(status="expired")

            # 撈一筆最舊的 pending（未過期），用鎖避免重取
            cmd = (
                DeviceCommand.objects.select_for_update(skip_locked=True)
                .filter(device=device, status="pending", expires_at__gt=now)
                .order_by("created_at")
                .first()
            )
            if cmd:
                cmd.status = "taken"
                cmd.taken_at = now
                cmd.save(update_fields=["status", "taken_at"])
                return JsonResponse(
                    {"cmd": cmd.command, "req_id": cmd.req_id, "payload": cmd.payload}
                )

        # 沒拿到 → 判斷是否超時
        if time.time() >= deadline:
            return HttpResponse(status=204)  # No Content
        time.sleep(0.2)  # 輕量輪詢間隔


# === 裝置回報：執行結果 ACK ===
@csrf_exempt
@require_POST
def device_ack(request):
    """
    輸入：
      { "serial_number": "...", "token": "...", "req_id": "...", "ok": true/false, "error": "" }
    """
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    serial = data.get("serial_number")
    token = data.get("token")
    req_id = data.get("req_id")
    ok = bool(data.get("ok"))
    error = data.get("error") or ""

    if not serial or not token or not req_id:
        return JsonResponse(
            {"error": "serial_number/token/req_id required"}, status=400
        )

    try:
        device = Device.objects.only("id", "serial_number", "token", "user_id").get(
            serial_number=serial
        )
    except Device.DoesNotExist:
        return JsonResponse({"error": "Device not found"}, status=404)

    if device.token != token:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    with transaction.atomic():
        cmd = (
            DeviceCommand.objects.select_for_update()
            .filter(device=device, req_id=req_id)
            .first()
        )
        if not cmd:
            return JsonResponse({"error": "Command not found"}, status=404)

        if cmd.status in ("done", "failed", "expired"):
            # 已處理過就當作成功回應（冪等）
            return JsonResponse({"ok": True})

        cmd.status = "done" if ok else "failed"
        cmd.error = "" if ok else (error or "unknown")
        cmd.done_at = timezone.now()
        cmd.save(update_fields=["status", "error", "done_at"])

        # （可選）在此觸發通知：成功/失敗
        # from notifications.services import notify_xxx
        # transaction.on_commit(lambda: notify_xxx(...))

    return JsonResponse({"ok": True})


@login_required  # 先確保使用者已登入
@require_POST  # 僅允許 POST，避免 GET 誤觸發副作用
def device_light_action(request, device_id, action):
    """
    建立一筆裝置控制指令，交由樹莓派 agent（/device_pull）取走執行。

    參數
    ----
    device_id : int
        要操作的裝置主鍵
    action : str
        'on' | 'off' | 'toggle' 三選一（對應設備端的 light_on/off/toggle）

    回傳
    ----
    - 若標頭含 X-Requested-With: XMLHttpRequest → JsonResponse
      內容包含 req_id/cmd_id，方便前端後續追蹤狀態
    - 否則 → redirect 到前一頁並顯示成功訊息
    """

    # 1) 輸入驗證：只接受 on/off/toggle
    if action not in ("on", "off", "toggle"):
        # 非法參數 → 400；若想非 AJAX 也維持 UX，可改為 messages.error + redirect
        return JsonResponse({"error": "invalid action"}, status=400)

    # 2) 取得裝置並做擁有者權限檢查
    device = get_object_or_404(Device, pk=device_id)
    if device.user_id != request.user.id:
        # 若未來支援「分享/授權」，此處可改為 user_can_control(user, device)
        return HttpResponseForbidden("你沒有權限操作此裝置。")

    # 3) 將人類語意 action 轉成設備端命令名稱（Pi 端 main() 會吃這個）
    cmd_map = {"on": "light_on", "off": "light_off", "toggle": "light_toggle"}
    cmd_name = cmd_map[action]

    # 4) 寫入一筆 pending 指令，等待 Pi 的 /device_pull 取走
    cmd = DeviceCommand.objects.create(
        device=device,
        command=cmd_name,
        payload={},  # 可放參數（如強度/時長），現為空物件
        req_id=uuid.uuid4().hex,  # Pi ack 用的唯一識別
        expires_at=timezone.now() + timedelta(minutes=2),  # 兩分鐘內有效
        status="pending",  # 讓 /device_pull 能查到
    )

    # 5) 依請求型態決定回傳格式
    #    - AJAX（XMLHttpRequest）→ 回 JSON
    #    - 非 AJAX → redirect + flash message
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {"ok": True, "req_id": cmd.req_id, "cmd_id": cmd.id}, status=200
        )

    messages.success(request, f"已送出 {action} 指令")
    return redirect(request.META.get("HTTP_REFERER", "my_devices"))
