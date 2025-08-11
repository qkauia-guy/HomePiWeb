from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse


def build_reset_url(request, user) -> str:
    # 使用者 ID 的 URL 安全編碼（uidb64），稍後可在後端解碼以查回使用者
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    # 為特定使用者建立密碼重設用的 token（與使用者狀態綁定、具時效）
    token = default_token_generator.make_token(user)
    # 編排 url：localhost/password_reset_confirm_custom/<uidb64>/<token>
    # 用路由「名稱」加上「參數」（如 uidb64、token、pk、slug）動態生成正確的 URL 路徑，避免硬編碼字串。
    path = reverse(
        "password_reset_confirm_custom", kwargs={"uidb64": uidb64, "token": token}
    )
    # 有https就使用不然就用http
    protocol = "https" if request.is_secure() else "http"
    domain = request.get_host()
    return f"{protocol}://{domain}{path}"
