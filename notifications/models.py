# notifications/models.py
from __future__ import annotations

from typing import Optional

from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.db.models import Q


class NotificationQuerySet(models.QuerySet):
    """提供常用的鏈式查詢輔助。"""

    def for_user(self, user) -> "NotificationQuerySet":
        return self.filter(user=user)

    def unread(self) -> "NotificationQuerySet":
        return self.filter(is_read=False)

    def read(self) -> "NotificationQuerySet":
        return self.filter(is_read=True)

    def valid(self) -> "NotificationQuerySet":
        """未設定過期或尚未過期者。"""
        now = timezone.now()
        return self.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))

    def expired(self) -> "NotificationQuerySet":
        now = timezone.now()
        return self.filter(expires_at__lt=now)

    def of_kind(self, kind: str) -> "NotificationQuerySet":
        return self.filter(kind=kind)

    def of_event(self, event: str) -> "NotificationQuerySet":
        return self.filter(event=event)

    def for_group(self, group) -> "NotificationQuerySet":
        return self.filter(group=group)

    def for_device(self, device) -> "NotificationQuerySet":
        return self.filter(device=device)


class Notification(models.Model):
    """
    使用者通知模型：
    - 以 GenericForeignKey 指向任意目標物件（群組、裝置、邀請…）
    - 以快篩欄位（group/device）優化常見列表查詢
    - 支援去重（dedup_key）與到期（expires_at）
    """

    KIND_MEMBER = "member"
    KIND_DEVICE = "device"

    KIND_CHOICES = [
        (KIND_MEMBER, "Member/Group"),
        (KIND_DEVICE, "Device"),
    ]

    # 收件人
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )

    # 類型＋事件
    kind = models.CharField(max_length=16, choices=KIND_CHOICES)
    event = models.CharField(
        max_length=64, db_index=True
    )  # e.g. member_added, device_offline

    # 顯示內容
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)

    # 指向任意目標（GFK）
    target_content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.SET_NULL
    )
    target_object_id = models.CharField(max_length=64, null=True, blank=True)
    target = GenericForeignKey("target_content_type", "target_object_id")

    # 快篩欄位（常見列表會用到）
    group = models.ForeignKey(
        "groups.Group",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )
    device = models.ForeignKey(
        "pi_devices.Device",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )

    # 已讀狀態
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # 去重鍵：同 user + dedup_key（非空）唯一
    dedup_key = models.CharField(max_length=200, blank=True, db_index=True)

    # 時間
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    # 其他結構化資訊
    meta = models.JSONField(default=dict, blank=True)

    # 自訂 QuerySet
    objects = NotificationQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=["user", "is_read", "created_at"]),
            models.Index(fields=["kind", "event"]),
            models.Index(fields=["group", "created_at"]),
            models.Index(fields=["device", "created_at"]),
        ]
        constraints = [
            # 只有 dedup_key 非空時，才強制 user+dedup_key 唯一
            models.UniqueConstraint(
                fields=["user", "dedup_key"],
                name="uniq_user_dedupkey_when_present",
                condition=~Q(dedup_key=""),
            ),
        ]
        ordering = ("-created_at",)  # 預設新到舊

    # --------------------
    # 便利屬性 / 方法
    # --------------------
    def __str__(self) -> str:
        return f"[{self.kind}/{self.event}] {self.title}"

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())

    def is_valid(self) -> bool:
        """向後相容的有效性判斷：未過期即有效。"""
        return not self.expires_at or self.expires_at > timezone.now()

    def mark_read(self, *, save: bool = True) -> None:
        """設為已讀；預設立即儲存。"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            if save:
                self.save(update_fields=["is_read", "read_at"])

    def mark_unread(self, *, save: bool = True) -> None:
        """設為未讀；預設立即儲存。"""
        if self.is_read or self.read_at is not None:
            self.is_read = False
            self.read_at = None
            if save:
                self.save(update_fields=["is_read", "read_at"])

    # --------------------
    # 類別方法（批次操作）
    # --------------------
    @classmethod
    def mark_all_for_user(cls, user, *, read: bool = True) -> int:
        """
        將使用者的通知一次設為已讀或未讀。
        回傳受影響筆數。
        """
        now = timezone.now()
        if read:
            qs = cls.objects.filter(user=user, is_read=False)
            return qs.update(is_read=True, read_at=now)
        else:
            qs = cls.objects.filter(user=user, is_read=True)
            return qs.update(is_read=False, read_at=None)

    @classmethod
    def purge_expired(cls) -> int:
        """
        刪除所有已過期通知。回傳刪除筆數。
        （建議配合 management command or cron/periodic job）
        """
        qs = cls.objects.filter(expires_at__lt=timezone.now())
        deleted, _ = qs.delete()
        return deleted

    # --------------------
    # GFK 安全設定輔助（選用）
    # --------------------
    def set_target(self, obj: Optional[models.Model]) -> None:
        """
        以單一方法安全設定 GFK，避免在外部漏設其中一個欄位。
        """
        if obj is None:
            self.target_content_type = None
            self.target_object_id = None
            return
        self.target_content_type = ContentType.objects.get_for_model(obj)
        self.target_object_id = str(getattr(obj, "pk", obj))
