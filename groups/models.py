from django.db import models
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from django.urls import reverse


class Group(models.Model):
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_groups",
    )
    # 用 through 記錄誰加了哪台裝置
    devices = models.ManyToManyField(
        "pi_devices.Device",
        through="GroupDevice",
        related_name="groups",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        # 你的群組詳情頁 URL name 若不同，請改掉 'group_detail'
        return reverse("group_detail", kwargs={"group_id": self.pk})


class GroupMembership(models.Model):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("operator", "Operator"),
        ("viewer", "Viewer"),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    group = models.ForeignKey(
        Group, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="viewer")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "group")]

    def __str__(self):
        return f"{self.user.email} @ {self.group.name} ({self.role})"


class GroupDevice(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    device = models.ForeignKey("pi_devices.Device", on_delete=models.CASCADE)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    added_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        unique_together = [("group", "device")]

    def __str__(self):
        who = self.added_by.email if self.added_by else "unknown"
        return f"{self.device.serial_number} -> {self.group.name} (by {who})"


class DeviceShareRequest(models.Model):
    """
    成員對「某群組 + 某台裝置」提出的一次性分享申請
    管理員核准後（approved）→ 可將該台裝置加入該群組（一次性）
    """

    STATUS_CHOICES = (
        ("pending", "待審核"),
        ("approved", "已核准"),
        ("rejected", "已拒絕"),
    )

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="device_share_requests",
    )
    group = models.ForeignKey(
        Group, on_delete=models.CASCADE, related_name="device_share_requests"
    )
    device = models.ForeignKey(
        "pi_devices.Device", on_delete=models.CASCADE, related_name="share_requests"
    )
    message = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="device_share_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # 只限制「未審核中的重複申請」
        constraints = [
            models.UniqueConstraint(
                fields=["requester", "group", "device"],
                condition=Q(status="pending"),
                name="uniq_pending_device_share_request",
            )
        ]
        indexes = [
            models.Index(fields=["group", "status"]),
            models.Index(fields=["requester", "status"]),
        ]

    def __str__(self):
        return f"[{self.status}] {self.requester} → {self.group} / {self.device}"


class GroupShareGrant(models.Model):
    """
    管理員對「某成員在某群組」開啟持續性分享權限（之後可直接將自己擁有的裝置加入）
    可設定到期日；過期或停用即失效
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="group_share_grants",
    )
    group = models.ForeignKey(
        Group, on_delete=models.CASCADE, related_name="share_grants"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="issued_share_grants",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "group"],
                condition=Q(is_active=True),
                name="uniq_active_group_share_grant",
            )
        ]
        indexes = [models.Index(fields=["group", "is_active"])]

    def is_valid(self) -> bool:
        return self.is_active and (
            self.expires_at is None or self.expires_at > timezone.now()
        )

    def __str__(self):
        state = "active" if self.is_valid() else "inactive"
        return f"Grant {self.user} @ {self.group} ({state})"
