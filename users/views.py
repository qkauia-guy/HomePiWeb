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
from django.utils.http import url_has_allowed_host_and_scheme

# from django.utils import timezone


@require_http_methods(["GET", "POST"])
def register_view(request):
    serial = (request.GET.get("serial") or "").strip()
    code = (request.GET.get("code") or "").strip()

    device = None
    if serial and code:
        # 用 iexact 避免大小寫/空白問題
        try:
            device = Device.objects.get(
                serial_number__iexact=serial,
                verification_code__iexact=code,
                is_bound=False,
            )
        except Device.DoesNotExist:
            # 帶了參數但不合法 → 顯示你已有的錯誤頁
            return render(request, "users/register_invalid.html", status=400)

    # === 已登入：綁定模式 ===
    if request.user.is_authenticated:
        if not device:
            # 已登入但沒有有效裝置參數 → 回主要頁
            return redirect("group_list")

        if request.method == "POST":
            # 不再要求 action=bind；只要 POST 就綁
            device.user = request.user
            device.is_bound = True
            device.save(update_fields=["user", "is_bound"])
            request.session.pop("pending_device_bind", None)
            messages.success(request, f"已將裝置 {device.serial_number} 綁定到你的帳號")
            redirect("my_devices")

        # GET：顯示綁定確認頁
        return render(request, "pi_devices/device_bind.html", {"device": device})

    # === 未登入：註冊模式 ===
    if device:
        # 備援：把待綁定資訊放 session，避免 next 遺失
        request.session["pending_device_bind"] = {"serial": serial, "code": code}

    form = UserRegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        if device:
            device.user = user
            device.is_bound = True
            device.save(update_fields=["user", "is_bound"])
            request.session.pop("pending_device_bind", None)
        login(request, user)
        messages.success(request, "註冊成功，歡迎！")
        return redirect("group_list")

    return render(request, "users/register.html", {"form": form, "device": device})


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

            # HTML 訊息（提醒：模板要用 |safe 才會渲染 HTML）
            role_msg = ""
            if getattr(user, "is_superadmin", False):
                role_msg = '<div style="color:green;">您是 SuperAdmin，可以管理所有設備與使用者。</div>'
            elif getattr(user, "is_admin", False):
                role_msg = '<div style="color:blue;">您是 Admin，擁有管理權限。</div>'
            else:
                role_msg = '<div style="color:gray;">您是一般使用者。</div>'

            html_msg = f"""
                <h2>👋 歡迎回來 {user.email}</h2>
                <p>目前身份：<strong>{getattr(user, 'get_role_display', lambda: 'User')()}</strong></p>
                {role_msg}
            """
            messages.success(request, html_msg)

            # ★ 優先使用 next（POST > GET），並做安全檢查
            nxt = request.POST.get("next") or request.GET.get("next")
            if nxt and url_has_allowed_host_and_scheme(
                nxt, allowed_hosts={request.get_host()}
            ):
                return redirect(nxt)

            # 沒帶 next 就回預設頁（你可改成 group_list）
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
