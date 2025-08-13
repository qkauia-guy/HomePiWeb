from django.contrib import admin
from .models import Invitation


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "group",
        "device",
        "invited_by",
        "role",
        "used_count",
        "max_uses",
        "expires_at",
        "is_active",
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
