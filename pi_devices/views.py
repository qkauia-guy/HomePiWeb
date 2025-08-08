from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
import json

from .models import Device


@csrf_exempt
@require_POST
def device_ping(request):
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

    # 3) 原子更新 last_ping + ip_address（同時驗證 token）
    updated = Device.objects.filter(serial_number=serial, token=token).update(
        last_ping=timezone.now(), ip_address=client_ip
    )

    if updated == 0:
        # 分辨：序號存在但 token 錯 vs. 根本沒這個序號
        if Device.objects.filter(serial_number=serial).exists():
            return JsonResponse({"error": "Unauthorized"}, status=401)
        return JsonResponse({"error": "Device not found"}, status=404)

    return JsonResponse({"status": "pong", "ip": client_ip})
