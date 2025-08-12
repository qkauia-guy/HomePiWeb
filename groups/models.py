from django.db import models
from django.conf import settings


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
