from django.contrib import admin
from django.utils import timezone
from django.db.models import Q

from .models import Notification


@admin.action(description="標記為已讀")
def mark_as_read(modeladmin, request, queryset):
    now = timezone.now()
    updated = queryset.filter(is_read=False).update(is_read=True, read_at=now)
    modeladmin.message_user(request, f"已將 {updated} 筆標記為已讀")


@admin.action(description="標記為未讀")
def mark_as_unread(modeladmin, request, queryset):
    updated = queryset.filter(is_read=True).update(is_read=False, read_at=None)
    modeladmin.message_user(request, f"已將 {updated} 筆標記為未讀")


@admin.action(description="刪除已過期通知")
def delete_expired(modeladmin, request, queryset):
    deleted, _ = queryset.filter(expires_at__lt=timezone.now()).delete()
    modeladmin.message_user(request, f"已刪除 {deleted} 筆過期通知")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "kind",
        "event",
        "title",
        "is_read",
        "created_at",
        "expires_at",
        "group",
        "device",
        "target_repr",
        "dedup_key",
    )
    list_filter = (
        "kind",
        "event",
        "is_read",
        "created_at",
        "expires_at",
        "group",
        "device",
    )
    search_fields = (
        "title",
        "body",
        "user__email",
        "dedup_key",
        "group__name",
        "device__serial_number",
        "device__name_cache",  # 若有暫存名稱欄位可保留，沒有可移除
        "target_object_id",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    actions = [mark_as_read, mark_as_unread, delete_expired]
    readonly_fields = ("created_at", "read_at")

    def target_repr(self, obj):
        if not obj.target_content_type_id or not obj.target_object_id:
            return "-"
        return f"{obj.target_content_type.model}#{obj.target_object_id}"

    target_repr.short_description = "Target"
