from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
import uuid
import secrets
import string
from datetime import timedelta


def gen_serial_number() -> str:
    # 例：PI-7A5D3C1B
    return f"PI-{uuid.uuid4().hex[:8].upper()}"


def gen_verification_code(length: int = 6) -> str:
    # 大寫 + 數字，使用 secrets 提升隨機性
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def gen_token() -> str:
    # 32位hex，若想 64 可 secrets.token_hex(32)
    return uuid.uuid4().hex


class Device(models.Model):
    serial_number = models.CharField(
        max_length=100,
        unique=True,
        editable=False,
        help_text="設備出廠序號，作為裝置的唯一識別",
        default=gen_serial_number,
        validators=[RegexValidator(r"^PI-[A-Z0-9]{8}$", "序號格式須為 PI-XXXXXXXX")],
    )
    verification_code = models.CharField(
        max_length=20,
        editable=False,
        help_text="用戶掃描 QRCode 後，需輸入的驗證碼",
        default=gen_verification_code,
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
        null=True,
        help_text="註冊連結專用 Token",
        default=gen_token,
    )
    is_bound = models.BooleanField(
        default=False, help_text="是否已綁定為 SuperAdmin，綁定後不可再次註冊"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="裝置在系統中建立的時間"
    )
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, help_text="綁定裝置的內網 IP"
    )
    last_ping = models.DateTimeField(null=True, blank=True, db_index=True)

    def is_online(self, window_seconds: int = 60) -> bool:
        """近 window_seconds 內有 ping 視為在線"""
        if not self.last_ping:
            return False
        return self.last_ping >= timezone.now() - timedelta(seconds=window_seconds)

    def __str__(self):
        return f"Device {self.serial_number} (Bound: {self.is_bound})"
