from django.db import models
import uuid
import random
import string


class Device(models.Model):
    # 系統自動產生的設備序號，例如：PI-7A5D3C1B（8 碼 UUID 片段）
    serial_number = models.CharField(
        max_length=100,
        unique=True,
        editable=False,
        help_text="設備出廠序號，作為裝置的唯一識別",
    )
    # 驗證碼，用戶掃描 QRCode 後需輸入，例如：8KD7QZ（6 碼隨機大寫+數字）
    verification_code = models.CharField(
        max_length=20, editable=False, help_text="用戶掃描 QRCode 後，需輸入的驗證碼"
    )
    # QRCode 註冊連結中的唯一 token，例如：c17e4aef27b046d5b75f78d3b209d901
    token = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
        null=True,
        help_text="註冊連結專用 Token",
    )
    # 是否已經綁定使用者（作為 SuperAdmin 註冊時綁定
    is_bound = models.BooleanField(
        default=False, help_text="是否已綁定為 SuperAdmin，綁定後不可再次註冊"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="裝置在系統中建立的時間"
    )

    def save(self, *args, **kwargs):
        # 若尚未設定 serial_number，則自動產生
        if not self.serial_number:
            self.serial_number = f"PI-{uuid.uuid4().hex[:8].upper()}"
        # 若尚未設定驗證碼，隨機產生 6 碼大寫英數字組合
        if not self.verification_code:
            self.verification_code = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=6)
            )  # 例如：8KD7QZ
        # 若尚未設定 token，使用 UUIDv4 產生唯一 token
        if not self.token:
            self.token = uuid.uuid4().hex  # 自動產生唯一 Token

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Device {self.serial_number} (Bound: {self.is_bound})"
