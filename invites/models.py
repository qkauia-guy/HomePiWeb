from django.db import models, IntegrityError
from django.conf import settings
from django.utils import timezone
import secrets


# ---- 產生 URL-safe 的邀請碼（約 32 字元） ----
def gen_code():
    # token_urlsafe 會含 A-Z a-z 0-9 - _
    # 這裡把 '_' 換成 '-'，純粹美觀/一致性（可不換）
    return secrets.token_urlsafe(24).replace("_", "-")


class Invitation(models.Model):
    group = models.ForeignKey("groups.Group", on_delete=models.CASCADE)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    email = models.EmailField(blank=True, null=True)
    role = models.CharField(max_length=20, default="operator")

    # None 代表無上限；預設 1 次
    max_uses = models.PositiveIntegerField(null=True, blank=True, default=1)
    used_count = models.PositiveIntegerField(default=0)

    expires_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    code = models.CharField(max_length=64, unique=True, db_index=True, editable=False)

    # 相容舊資料：單裝置欄位仍保留，但允許為空
    # 不希望刪掉裝置就把邀請整個 cascade 掉，改 SET_NULL
    device = models.ForeignKey(
        "pi_devices.Device", on_delete=models.SET_NULL, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # ---- 邏輯判斷：目前是否可用 ----
    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False
        return True

    # ---- 消費一次（接受邀請時呼叫）----
    def consume(self, commit: bool = True):
        """
        成功消費一次邀請。若達到 max_uses，會自動把 is_active 關掉。
        並不在此方法內加鎖；請在外層 view 已搭配
        select_for_update() + transaction.atomic() 來避免併發。
        """
        if not self.is_valid():
            raise ValueError("Invitation is not valid")

        self.used_count = (self.used_count or 0) + 1
        if self.max_uses is not None and self.used_count >= self.max_uses:
            self.is_active = False

        if commit:
            self.save(update_fields=["used_count", "is_active"])

    # ---- 存檔時自動帶入唯一 code（含碰撞重試）----
    def save(self, *args, **kwargs):
        if not self.code:
            # 最多重試 5 次；極低機率才會碰撞
            for _ in range(5):
                self.code = gen_code()
                try:
                    return super().save(*args, **kwargs)
                except IntegrityError as e:
                    # 只針對 code 唯一鍵碰撞重試；其他錯直接拋出
                    if "invites_invitation.code" in str(e):
                        self.code = None
                        continue
                    raise
        # 已有 code（或重試已成功）
        return super().save(*args, **kwargs)

    def __str__(self):
        state = "active" if self.is_valid() else "inactive"
        return f"INV {self.code} @ {self.group_id} ({state})"


class InvitationDevice(models.Model):
    """一張邀請卡上，逐台裝置的權限設定（配合多裝置場景）"""

    invitation = models.ForeignKey(
        Invitation, on_delete=models.CASCADE, related_name="device_items"
    )
    device = models.ForeignKey("pi_devices.Device", on_delete=models.CASCADE)
    can_control = models.BooleanField(default=True)  # 之後可擴充更多權限欄位

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["invitation", "device"], name="uniq_invitation_device"
            )
        ]

    def __str__(self):
        return f"{self.invitation.code} -> {self.device_id} ({'control' if self.can_control else 'view'})"
