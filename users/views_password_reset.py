from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods

# 官方提供的密碼重設 Token 產生/驗證器。
from django.contrib.auth.tokens import default_token_generator

# 內建寄信 API，用於正式環境寄送重設連結（內文自訂）。
from django.core.mail import send_mail

# 將位元組安全轉成字串；常與 urlsafe_base64_decode 搭配使用
from django.utils.encoding import force_str

# 從 URL-safe Base64 還原出原始位元組（在此用來還原 user.pk）
from django.utils.http import urlsafe_base64_decode

# 反向解析路由組成重設連結（可改用
from .utils.password_reset import build_reset_url

from django.db import transaction
from notifications.services import notify_password_changed

User = get_user_model()  # 取得專案中實際使用的 User 模型(django.contrib.auth 模組)


# 僅允許 GET 顯示頁面、POST 提交 Email。限制 HTTP 動詞是基本面安全與行為約束。
@require_http_methods(["GET", "POST"])
def password_reset_request_view(request):
    """
    忘記密碼入口：
    - PASSWORD_RESET_SEND_EMAIL=False：頁面直接顯示重設連結（便於開發/內部測試，不經過郵件管道）
    - True：寄送 Email（正式環境）
    """
    reset_url = None  # 用於「不寄信模式」在頁面顯示的重設連結
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        # 不洩漏帳號是否存在：用模糊提示訊息避免攻擊者藉由回應判斷 Email 是否註冊
        user = User.objects.filter(email__iexact=email, is_active=True).first()

        if user:
            # 生成重設連結：
            # - uidb64：將 user.pk 經 URL-safe Base64 編碼（適合放在 URL），後端會再 decode 取回 pk[13][16]
            # - token：default_token_generator.make_token(user) 依使用者目前狀態（pk、password hash、last_login、timestamp、email 等）計算，一次性且具時效，驗證用 check_token[6][9]
            # - 透過反向解析 reverse 以路由名稱+參數產生 path，避免硬編碼 URL；再組合成完整 URL（協定/網域取自 request）[1][8]
            link = build_reset_url(request, user)

            if getattr(settings, "PASSWORD_RESET_SEND_EMAIL", False):
                # 正式環境：寄 Email，內含完整重設連結
                subject = "重設你的密碼"
                body = (
                    f"您好，\n\n"
                    f"請點擊以下連結重設密碼：\n{link}\n\n"
                    f"若非您本人操作，請忽略此信。"
                )
                # send_mail 由 settings 設定寄件者；建議在正式環境配置正確的 EMAIL_BACKEND/SMTP
                send_mail(
                    subject,
                    body,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
                # 提示語維持「不洩漏帳號是否存在」的口吻
                messages.info(request, "若該 Email 有帳號，重設連結已寄出。")
            else:
                # 開發/內部模式：直接在頁面展示重設連結，避免寄信流程
                reset_url = link
                messages.success(request, "已產生重設連結（開發/內部用）。")
        else:
            # 無論是否找到使用者，回應都採用同樣語句避免側信道洩漏
            messages.info(request, "若該 Email 有帳號，將提供重設方式。")

    # 渲染輸入 Email 的頁面；若為不寄信模式，模板可顯示 reset_url 供測試點擊
    return render(
        request, "users/password_reset_request.html", {"reset_url": reset_url}
    )


"""
設定新密碼（邏輯與 Django 內建 Confirm 流程一致）：
- 先以 uidb64 還原出 user.pk 並查詢 user
- 再以 user+token 執行 check_token 驗證有效性/時效性
- 通過後呈現/處理 SetPasswordForm；成功儲存會 set_password 並使舊 token 自然失效（因 password hash 改變）
"""


@require_http_methods(["GET", "POST"])
def password_reset_confirm_view(request, uidb64, token):
    # 1) 解碼使用者
    user = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid, is_active=True)
    except Exception:
        user = None

    # 2) 驗證 token
    if not user or not default_token_generator.check_token(user, token):
        messages.error(request, "重設連結無效或已過期，請重新申請。")
        return redirect("password_reset_request")

    # 3) 建立/驗證表單
    if request.method == "POST":
        form = SetPasswordForm(user, data=request.POST)
        if form.is_valid():
            form.save()  # set_password + save

            # 來源 IP / UA（僅做紀錄）
            xff = request.META.get("HTTP_X_FORWARDED_FOR")
            client_ip = (
                xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
            )
            ua = request.META.get("HTTP_USER_AGENT", "")

            # 提交成功後才發通知
            transaction.on_commit(
                lambda: notify_password_changed(
                    user=user, actor=user, ip=client_ip, user_agent=ua
                )
            )

            messages.success(request, "密碼已更新，請使用新密碼登入。")
            return redirect("login")
        # 表單無效 → 繼續往下 render，帶出錯誤
    else:
        form = SetPasswordForm(user)

    # 4) 一定要有回傳：初次 GET 或表單無效
    return render(request, "users/password_reset_confirm.html", {"form": form})
