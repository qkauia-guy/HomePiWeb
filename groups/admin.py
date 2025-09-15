from django.contrib import admin
from .models import (
    Group,
    GroupMembership,
    GroupDevice,
    DeviceShareRequest,
    GroupShareGrant,
    GroupDevicePermission,
)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "device_count",
        "member_count",
        "created_at",
    )
    search_fields = ("name", "owner__email")
    list_select_related = ("owner",)
    ordering = ("-created_at",)

    def device_count(self, obj):
        return obj.devices.count()

    device_count.short_description = "裝置數"

    def member_count(self, obj):
        return obj.memberships.count()

    member_count.short_description = "成員數"


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "group", "role_zh", "joined_at")
    list_filter = ("role", "group")
    search_fields = ("user__email", "group__name")
    list_select_related = ("user", "group")
    ordering = ("-joined_at",)

    @admin.display(description="角色")
    def role_zh(self, obj: GroupMembership):
        # 顯示中文角色名稱
        mapping = {
            "admin": "管理員",
            "operator": "操作員",
            "viewer": "檢視者",
        }
        return mapping.get(obj.role, obj.role)


@admin.register(GroupDevice)
class GroupDeviceAdmin(admin.ModelAdmin):
    list_display = ("group", "device", "added_by", "added_at", "note")
    search_fields = ("group__name", "device__serial_number", "added_by__email")
    list_select_related = ("group", "device", "added_by")
    ordering = ("-added_at",)


@admin.register(DeviceShareRequest)
class DeviceShareRequestAdmin(admin.ModelAdmin):
    list_display = (
        "requester",
        "group",
        "device",
        "status",
        "created_at",
        "reviewed_by",
        "reviewed_at",
    )
    list_filter = ("status", "group")
    search_fields = ("requester__email", "group__name", "device__serial_number")
    list_select_related = ("requester", "group", "device", "reviewed_by")
    ordering = ("-created_at",)


@admin.register(GroupShareGrant)
class GroupShareGrantAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "group",
        "is_active",
        "expires_at",
        "created_by",
        "created_at",
    )
    list_filter = ("is_active", "group")
    search_fields = ("user__email", "group__name", "created_by__email")
    list_select_related = ("user", "group", "created_by")
    ordering = ("-created_at",)


@admin.register(GroupDevicePermission)
class GroupDevicePermissionAdmin(admin.ModelAdmin):
    list_display = ("group", "device", "user", "can_control", "updated_at")
    list_filter = ("group", "can_control")
    search_fields = ("group__name", "device__serial_number", "user__email")
    list_select_related = ("group", "device", "user")
    ordering = ("-updated_at",)
