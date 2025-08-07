# users/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from pi_devices.models import Device
from .forms import UserRegisterForm


def register_view(request):
    serial = request.GET.get("serial")
    code = request.GET.get("code")

    # 檢查設備是否存在與驗證碼正確
    try:
        device = Device.objects.get(
            serial_number=serial, verification_code=code, is_bound=False
        )
    except Device.DoesNotExist:
        messages.error(request, "裝置驗證失敗，請確認 QRCode 是否正確或已被註冊")
        return render(request, "users/register_invalid.html")

    if request.method == "POST":
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.device = device  # 綁定裝置
            user.save()
            device.is_bound = True  # 更新裝置狀態
            device.save()
            messages.success(request, "註冊成功！")
            return redirect("login")
    else:
        form = UserRegisterForm()

    return render(request, "users/register.html", {"form": form})
