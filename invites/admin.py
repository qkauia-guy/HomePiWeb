from django.contrib import admin
from .models import Invitation, InvitationDevice


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        "code_zh",
        "group",
        "device",
        "invited_by",
        "role_zh",
        "max_uses",
        "used_count",
        "expires_at",
        "is_active_zh",
        "created_at",
    )
    list_filter = ("is_active", "role", "group")
    search_fields = (
        "code",
        "group__name",
        "device__serial_number",
        "invited_by__email",
    )
    list_select_related = ("group", "device", "invited_by")
    ordering = ("-created_at",)

    @admin.display(description="邀請碼")
    def code_zh(self, obj: Invitation):
        return obj.code

    @admin.display(description="角色")
    def role_zh(self, obj: Invitation):
        mapping = {
            "operator": "操作員",
            "admin": "管理員",
            "superadmin": "超級管理員",
        }
        return mapping.get(obj.role, obj.role)

    @admin.display(boolean=True, description="啟用")
    def is_active_zh(self, obj: Invitation):
        return obj.is_active


@admin.register(InvitationDevice)
class InvitationDeviceAdmin(admin.ModelAdmin):
    list_display = ("invitation", "device", "can_control")
    list_filter = ("can_control",)
    search_fields = ("invitation__code", "device__serial_number")
    list_select_related = ("invitation", "device")
