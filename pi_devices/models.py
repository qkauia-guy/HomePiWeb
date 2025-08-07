from django.db import models


class Device(models.Model):
    serial_number = models.CharField(
        max_length=100,
        unique=True,
        help_text="設備出廠序號，作為裝置的唯一識別",
    )
    verification_code = models.CharField(
        max_length=20, help_text="用戶掃描 QRCode 後，需輸入的驗證碼"
    )
    is_bound = models.BooleanField(
        default=False, help_text="是否已綁定為 SuperAdmin，綁定後不可再次註冊"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="裝置在系統中建立的時間"
    )

    def __str__(self):
        return f"Device {self.serial_number} (Bound: {self.is_bound})"
