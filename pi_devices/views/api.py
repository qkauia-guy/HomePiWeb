# pi_devices/views/api.py
import json, time
from datetime import timedelta
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from ..models import Device, DeviceCommand
from notifications.services import notify_device_ip_changed, notify_user_online
from django.utils.text import slugify
from ..models import DeviceCapability


csrf_exempt


@require_POST
def device_ping(request):
    body = request.body.decode("utf-8") if request.body else ""
    if not body:
        return JsonResponse({"error": "Empty body"}, status=400)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    serial = data.get("serial_number")
    token = data.get("token")
    if not serial:
        return JsonResponse({"error": "No serial_number"}, status=400)
    if not token:
        return JsonResponse({"error": "No token"}, status=401)

    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    client_ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")

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
            threshold = now - timedelta(seconds=window)

            was_online = False
            if owner_id:
                was_online = bool(device.last_ping and device.last_ping >= threshold)
                if not was_online:
                    was_online = (
                        Device.objects.filter(
                            user_id=owner_id, last_ping__gte=threshold
                        )
                        .exclude(pk=device.pk)
                        .exists()
                    )

            old_ip = device.ip_address or None
            ip_changed = old_ip != client_ip

            # ✅ 更新心跳/IP
            device.last_ping = now
            device.ip_address = client_ip
            device.save(update_fields=["last_ping", "ip_address"])

            # ✅ 如果這次帶了 capabilities，就做 upsert（第一次開機/手動重新偵測會用到）
            caps = data.get("caps")
            caps_changed = 0
            if isinstance(caps, list) and caps:
                # 若要把「沒出現在本次回報的舊能力」自動停用，傳 True
                caps_changed = sync_caps(device, caps, auto_disable_unseen=False)

            # 上線/變更 IP 通知照舊
            if owner_id and not was_online:
                from django.contrib.auth import get_user_model

                User = get_user_model()
                subject_user = User.objects.filter(pk=owner_id).first()
                if subject_user:
                    transaction.on_commit(lambda: notify_user_online(user=subject_user))

            if ip_changed and owner_id:
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

    # 可選把變更數量回傳，前端要用可讀
    resp = {"status": "pong", "ip": client_ip}
    if isinstance(data.get("caps"), list):
        resp["caps_processed"] = True
    return JsonResponse(resp)


@csrf_exempt
@require_POST
def device_pull(request):
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

    deadline = time.time() + max_wait
    while True:
        with transaction.atomic():
            now = timezone.now()
            DeviceCommand.objects.filter(
                device=device, status="pending", expires_at__lte=now
            ).update(status="expired")
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
        if time.time() >= deadline:
            return HttpResponse(status=204)
        time.sleep(0.2)


@csrf_exempt
@require_POST
def device_ack(request):
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

    from django.utils import timezone as djtz

    with transaction.atomic():
        cmd = (
            DeviceCommand.objects.select_for_update()
            .filter(device=device, req_id=req_id)
            .first()
        )
        if not cmd:
            return JsonResponse({"error": "Command not found"}, status=404)
        if cmd.status in ("done", "failed", "expired"):
            return JsonResponse({"ok": True})
        cmd.status = "done" if ok else "failed"
        cmd.error = "" if ok else (error or "unknown")
        cmd.done_at = djtz.now()
        cmd.save(update_fields=["status", "error", "done_at"])
    return JsonResponse({"ok": True})


def sync_caps(device, caps: list[dict], auto_disable_unseen: bool = False) -> int:
    """
    依據裝置回報的 capabilities（list of dict）做 upsert：
      key = (slug)（你模型 unique_together 已是 (device, slug)）
      欄位：kind/name/config/order/enabled
    回傳：此次處理的項目數（含 create/update）
    """
    # 預先取既有資料，避免 N+1
    current = {c.slug: c for c in device.capabilities.all()}
    seen = set()
    changed = 0

    for item in caps:
        if not isinstance(item, dict):
            continue
        kind = (item.get("kind") or "").strip() or "light"
        name = (item.get("name") or "").strip() or kind
        slug = (item.get("slug") or slugify(name))[:50] or "cap"
        config = item.get("config") or {}
        order = int(item.get("order") or 0)
        enabled = bool(item.get("enabled", True))

        seen.add(slug)

        if slug in current:
            obj = current[slug]
            dirty = False
            if obj.kind != kind:
                obj.kind = kind
                dirty = True
            if obj.name != name:
                obj.name = name
                dirty = True
            if obj.config != config:
                obj.config = config
                dirty = True
            if obj.order != order:
                obj.order = order
                dirty = True
            if obj.enabled != enabled:
                obj.enabled = enabled
                dirty = True
            if dirty:
                obj.save()
                changed += 1
        else:
            DeviceCapability.objects.create(
                device=device,
                kind=kind,
                name=name,
                slug=slug,
                config=config,
                order=order,
                enabled=enabled,
            )
            changed += 1

    # （可選）把這次沒回報到的舊能力標為 disabled
    if auto_disable_unseen:
        for slug, obj in current.items():
            if slug not in seen and obj.enabled:
                obj.enabled = False
                obj.save(update_fields=["enabled"])
                changed += 1

    return changed
