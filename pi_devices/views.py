from django.shortcuts import render, get_object_or_404
from .models import Device
from utils.qrcode_utils import generate_qr_code_base64
from ..users.forms import UserRegisterForm
from django.contrib import messages


def register_view(request):
    serial = request.GET.get("serial")
    code = request.GET.get("code")

    # 根據 serial + code 找出對應設備，取得 token
    from pi_devices.models import Device

    try:
        device = Device.objects.get(serial_number=serial, verification_code=code)
        token = device.token
    except Device.DoesNotExist:
        return render(
            request,
            "users/register.html",
            {
                "form": None,
                "error": "無效的設備資訊，請確認序號與驗證碼是否正確",
            },
        )

    if request.method == "POST":
        form = UserRegisterForm(request.POST, token=token)
        if form.is_valid():
            form.save()
            return redirect("login")  # 或換成你想導向的頁面
    else:
        print(form.errors)  # ⛳ 看這個！！

    return render(request, "users/register.html", {"form": form})
