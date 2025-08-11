import socket
from django.shortcuts import render, redirect
from django.contrib import messages
from pi_devices.models import Device
from .forms import UserRegisterForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.http import require_POST


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
        form = UserRegisterForm(request.POST or None, token=device.token)

        if form.is_valid():
            user = form.save(commit=False)
            user.device = device  # 綁定裝置
            user.role = "superadmin"
            user.save()  # ⏎ 儲存資料庫
            device.is_bound = True  # 更新裝置狀態
            device.save()
            messages.success(request, "註冊成功！")
            return redirect("login")
    else:
        form = UserRegisterForm(token=device.token)

    return render(request, "users/register.html", {"form": form})


def is_device_online(ip_address, port=8800, timeout=2):
    try:
        with socket.create_connection((ip_address, port), timeout=timeout):
            return True
    except Exception:
        return False


def login_view(request):
    form = AuthenticationForm(data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            try:
                device = user.device  # 前提：user 有 OneToOne 或 ForeignKey 到 Device
                if is_device_online(device.ip_address):
                    messages.success(request, "設備在線 ✅")
                else:
                    messages.warning(request, "設備不在線 ❌")
            except Exception as e:
                messages.warning(request, f"找不到綁定設備或無法連線：{e}")

            return redirect("home")

    return render(request, "users/login.html", {"form": form})


@login_required
def home_view(request):
    return render(request, "home.html", {"user": request.user})


@require_POST
@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "你已登出。")
    return redirect("login")
