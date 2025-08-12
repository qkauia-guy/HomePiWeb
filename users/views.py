import socket
from django.shortcuts import render, redirect
from django.contrib import messages
from pi_devices.models import Device
from .forms import UserRegisterForm
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.http import require_POST, require_http_methods
from django.db import transaction

# from django.utils import timezone


@require_http_methods(["GET", "POST"])
def register_view(request):
    serial = request.GET.get("serial")
    code = request.GET.get("code")

    # 參數缺失 → 直接失敗頁
    if not serial or not code:
        messages.error(request, "裝置驗證失敗，請確認 QRCode 是否正確或已被註冊")
        return render(request, "users/register_invalid.html")

    try:
        # 加鎖避免併發重複綁定（兩個人同時註冊同一台）
        with transaction.atomic():
            device = Device.objects.select_for_update().get(  # 資料庫層級鎖
                serial_number=serial, verification_code=code, is_bound=False
            )

            if request.method == "POST":
                # 將 token 帶進表單驗證（表單內要驗證 token 與 device.token 一致）
                form = UserRegisterForm(request.POST, token=device.token)
                if form.is_valid():
                    user = form.save(commit=False)
                    user.device = device
                    user.role = "superadmin"
                    user.save()

                    # 綁定完成 → 設定裝置狀態
                    device.is_bound = True
                    # （可選）記錄綁定時間 / 清空驗證碼避免再次使用 / 旋轉 token
                    # device.bound_at = timezone.now()
                    # device.verification_code = None
                    # device.token = None
                    device.save(update_fields=["is_bound"])  # 視需求加上其它欄位

                    messages.success(request, "註冊成功！")
                    return redirect("login")
            else:
                form = UserRegisterForm(token=device.token)

    except Device.DoesNotExist:
        messages.error(request, "裝置驗證失敗，請確認 QRCode 是否正確或已被註冊")
        return render(request, "users/register_invalid.html")

    return render(request, "users/register.html", {"form": form})


def is_device_online(ip_address, port=8800, timeout=2):
    try:
        with socket.create_connection((ip_address, port), timeout=timeout):
            return True
    except Exception:
        return False


def login_view(request):
    form = AuthenticationForm(request, data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # HTML 訊息
            role_msg = ""
            if user.is_superadmin:
                role_msg = '<div style="color:green;">您是 SuperAdmin，可以管理所有設備與使用者。</div>'
            elif user.is_admin:
                role_msg = '<div style="color:blue;">您是 Admin，擁有管理權限。</div>'
            else:
                role_msg = '<div style="color:gray;">您是一般使用者。</div>'

            html_msg = f"""
                <h2>👋 歡迎回來 {user.email}</h2>
                <p>目前身份：<strong>{user.get_role_display()}</strong></p>
                {role_msg}
            """

            messages.success(request, html_msg)

            return redirect("home")
        else:
            messages.error(request, "帳號或密碼不正確，請再試一次。")

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
