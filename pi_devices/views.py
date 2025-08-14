from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
import json

from .models import Device
from .forms import DeviceNameForm, BindDeviceForm
from django.db import transaction
from django.views.decorators.http import require_http_methods


@login_required
def my_devices(request):
    devices = request.user.devices.all().order_by("-created_at")
    return render(request, "pi_devices/my_devices.html", {"devices": devices})


@login_required
def device_edit_name(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if device.user_id != request.user.id:
        return HttpResponseForbidden("你沒有權限編輯這台裝置。")

    if request.method == "POST":
        form = DeviceNameForm(request.POST, instance=device)
        if form.is_valid():
            form.save()
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

            messages.success(request, f"綁定成功！({device.serial_number})")
            return redirect("my_devices")
        # 表單失敗 → 繼續往下 render，模板會顯示錯誤
    else:
        # 支援從 URL 預填 ?serial=&code=
        initial = {}
        if request.GET.get("serial"):
            initial["serial_number"] = request.GET["serial"].strip()
        if request.GET.get("code"):
            initial["verification_code"] = request.GET["code"].strip()
        form = BindDeviceForm(initial=initial)

    return render(request, "pi_devices/device_bind.html", {"form": form})


@login_required
def device_unbind(request, pk):
    device = get_object_or_404(Device, pk=pk)
    if device.user_id != request.user.id:
        return HttpResponseForbidden("你沒有權限操作此裝置。")

    if request.method == "POST":
        with transaction.atomic():
            device = Device.objects.select_for_update().get(pk=device.pk)
            device.user = None
            device.is_bound = False
            device.save(update_fields=["user", "is_bound"])
        messages.success(request, "已解除綁定。")
        return redirect("my_devices")

    return render(request, "pi_devices/device_unbind_confirm.html", {"device": device})


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
