from django.conf import settings
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone
import uuid, secrets, string
from datetime import timedelta
from django.urls import reverse, NoReverseMatch


def gen_serial_number() -> str:
    return f"PI-{uuid.uuid4().hex[:8].upper()}"


def gen_verification_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def gen_token() -> str:
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

    # ✅ 新增：多台裝置歸屬同一使用者
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="devices",
        help_text="裝置擁有者（綁定後）",
    )

    is_bound = models.BooleanField(default=False, help_text="是否已被某位使用者綁定")
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="裝置在系統中建立的時間"
    )
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, help_text="綁定裝置的內網 IP"
    )
    last_ping = models.DateTimeField(null=True, blank=True, db_index=True)
    display_name = models.CharField(
        max_length=100, blank=True, help_text="自訂裝置顯示名稱；若留空則顯示序號"
    )

    def is_online(self, window_seconds: int = 60) -> bool:
        if not self.last_ping:
            return False
        return self.last_ping >= timezone.now() - timedelta(seconds=window_seconds)

    def name(self) -> str:
        return self.display_name or self.serial_number

    def __str__(self):
        return f"{self.name()} (SN: {self.serial_number}, Bound: {self.is_bound})"

    def get_absolute_url(self):
        # 若有裝置詳情頁就導去那；沒有就退到「我的裝置」列表。
        try:
            # 目前應該沒有這頁面
            return reverse("/", kwargs={"device_id": self.pk})
        except NoReverseMatch:
            return reverse("my_devices")

    @property
    def label(self):
        return self.display_name or self.serial_number

    class Meta:
        indexes = [
            models.Index(fields=["is_bound"]),
            models.Index(fields=["last_ping"]),
            models.Index(fields=["user"]),  # ✅ 查詢「我的裝置」更快
        ]


class DeviceCommand(models.Model):
    STATUS_CHOICES = [
        ("pending", "pending"),
        ("taken", "taken"),
        ("done", "done"),
        ("failed", "failed"),
        ("expired", "expired"),
    ]

    device = models.ForeignKey(
        "pi_devices.Device", on_delete=models.CASCADE, related_name="commands"
    )
    command = models.CharField(max_length=50)  # 例如：unlock
    payload = models.JSONField(default=dict, blank=True)
    req_id = models.CharField(max_length=64, db_index=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True
    )
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    taken_at = models.DateTimeField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def is_expired(self) -> bool:
        return bool(self.expires_at and timezone.now() >= self.expires_at)

    class Meta:
        indexes = [
            models.Index(fields=["device", "status"]),
            models.Index(fields=["req_id"]),
        ]

    def __str__(self):
        return f"{self.device_id} {self.command} [{self.status}]"
