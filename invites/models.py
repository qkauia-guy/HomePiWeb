from django.db import models
from django.conf import settings
from django.utils import timezone
import secrets

"""
token_urlsafe(nbytes=None) 函式：
這個函式會產生一個隨機的文字字串
它的內容由 URL 和檔案系統安全的英文字母（A-Z, a-z, 0-9, -, _）組成。這意味著生成的字串可以直接用在網址中，而不需要額外的編碼處理。
函式會先產生 nbytes 個隨機位元組（bytes），然後再將這些位元組編碼成字串。
24：你傳入的參數 24 代表它會產生 24 個隨機位元組。這 24 個位元組經過 Base64 URL-safe 編碼後，會變成一個大約 32 字元長的字串。
"""


def gen_code():
    return secrets.token_urlsafe(24)


class Invitation(models.Model):
    # unique=True 和 db_index=True 確保每個邀請碼都是唯一的，並且可以快速被資料庫查詢。
    code = models.CharField(
        max_length=255, unique=True, default=gen_code, db_index=True
    )
    # 資料關連 groups.Group 和 pi_devices.Device
    group = models.ForeignKey(
        "groups.Group", on_delete=models.CASCADE, related_name="invitations"
    )
    device = models.ForeignKey(
        "pi_devices.Device", on_delete=models.CASCADE, related_name="invitations"
    )
    # 資料關連 指向 Django 的使用者模型（settings.AUTH_USER_MODEL）記錄是誰發出了這個邀請。
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_invitations",
    )
    email = models.EmailField(blank=True, null=True)  # 限定信箱
    role = models.CharField(max_length=20, default="operator")  # 受邀加入群組後的角色
    max_uses = models.PositiveIntegerField(default=1)
    used_count = models.PositiveIntegerField(
        default=0
    )  # 每次成功使用後，consume 方法會將此欄位加一
    expires_at = models.DateTimeField(null=True, blank=True)  # 設定邀請碼的失效時間
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # 檢查邀請碼是否有效(它會依序檢查 is_active、expires_at（是否過期）和 used_count（是否超過使用次數），並回傳 True 或 False。)
    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        if self.used_count >= self.max_uses:
            return False
        return True

    # 當邀請碼被成功使用後，會呼叫此方法。它會增加 used_count
    # 如果使用次數達到 max_uses，則會將 is_active 設為 False，並將變更儲存到資料庫中。
    def consume(self):
        self.used_count += 1
        if self.used_count >= self.max_uses:
            self.is_active = False
        self.save(update_fields=["used_count", "is_active"])

    def __str__(self):
        return f"{self.group.name} / {self.device.serial_number} / {self.code[:6]}…"
