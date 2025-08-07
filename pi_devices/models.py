from django.db import models
import uuid
import random
import string


class Device(models.Model):
    serial_number = models.CharField(
        max_length=100,
        unique=True,
        editable=False,
        help_text="設備出廠序號，作為裝置的唯一識別",
    )
    verification_code = models.CharField(
        max_length=20, editable=False, help_text="用戶掃描 QRCode 後，需輸入的驗證碼"
    )
    is_bound = models.BooleanField(
        default=False, help_text="是否已綁定為 SuperAdmin，綁定後不可再次註冊"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="裝置在系統中建立的時間"
    )

    def save(self, *args, **kwargs):
        if not self.serial_number:
            self.serial_number = (
                f"PI-{uuid.uuid4().hex[:8].upper()}"  # 例如：PI-7A5D3C1B
            )
        if not self.verification_code:
            self.verification_code = "".join(
                random.choices(string.ascii_uppercase + string.digits, k=6)
            )  # 例如：8KD7QZ
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Device {self.serial_number} (Bound: {self.is_bound})"
