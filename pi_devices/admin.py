# admin.py
from datetime import timedelta

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Device, DeviceCapability, DeviceCommand, DeviceSchedule

# # 線上判斷視窗（可在 settings.py 設 DEVICE_ONLINE_WINDOW_SECONDS 覆寫）
ONLINE_WINDOW_SECONDS = getattr(settings, "DEVICE_ONLINE_WINDOW_SECONDS", 60)


# ========== 自訂篩選 ==========
class OnlineStatusFilter(admin.SimpleListFilter):
    title = "在線狀態"
    parameter_name = "online"

    def lookups(self, request, model_admin):
        return (("1", "在線"), ("0", "離線"))

    def queryset(self, request, queryset):
        now = timezone.now()
        window = now - timedelta(seconds=ONLINE_WINDOW_SECONDS)
        if self.value() == "1":
            return queryset.filter(last_ping__gte=window)
        if self.value() == "0":
            return queryset.filter(
                models.Q(last_ping__isnull=True) | models.Q(last_ping__lt=window)
            )
        return queryset


class CapabilityKindFilter(admin.SimpleListFilter):
    title = "能力種類"
    parameter_name = "cap_kind"

    def lookups(self, request, model_admin):
        # 直接用 model 的 choices
        return DeviceCapability.KIND_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(capabilities__kind=self.value()).distinct()
        return queryset


# ========== Inline：裝置下直接管理能力 ==========
class DeviceCapabilityInline(admin.TabularInline):
    model = DeviceCapability
    extra = 0
    fields = ("enabled", "order", "name", "kind", "slug", "config")
    ordering = ("order", "id")
    show_change_link = True


# ========== Device 後台 ==========
@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    # 顯示欄
    list_display = (
        "id",
        "display_name_or_sn",  # 名稱
        "serial_number_zh",
        "owner_link",  # 擁有者
        "online",  # 線上
        "capabilities_count",  # 能力數
        "capabilities_preview",  # 能力預覽
        "ip_address_zh",
        "last_ping_zh",
        "created_at_zh",
    )
    list_select_related = ("user",)
    list_filter = (OnlineStatusFilter, CapabilityKindFilter, "created_at")
    search_fields = (
        "serial_number",
        "display_name",
        "user__email",
        "capabilities__name",
        "capabilities__slug",
    )
    ordering = ("-created_at",)
    empty_value_display = "-"
    readonly_fields = (
        "serial_number",
        "created_at",
        "last_ping",
    )
    inlines = [DeviceCapabilityInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # 預取關聯，避免 N+1
        return qs.select_related("user").prefetch_related("capabilities")

    # ------- 自訂欄位 -------
    @admin.display(description="名稱")
    def display_name_or_sn(self, obj: Device):
        return obj.display_name or obj.serial_number

    @admin.display(description="序號")
    def serial_number_zh(self, obj: Device):
        return obj.serial_number

    @admin.display(description="擁有者", ordering="user__email")
    def owner_link(self, obj: Device):
        if not obj.user_id:
            return self.empty_value_display
        User = get_user_model()
        opts = User._meta
        url = reverse(
            f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.user_id]
        )
        label = (
            getattr(obj.user, "email", None)
            or getattr(obj.user, "username", None)
            or str(obj.user_id)
        )
        return format_html('<a href="{}">{}</a>', url, label)

    @admin.display(boolean=True, description="在線", ordering="last_ping")
    def online(self, obj: Device):
        if not obj.last_ping:
            return False
        return obj.last_ping >= timezone.now() - timedelta(
            seconds=ONLINE_WINDOW_SECONDS
        )

    @admin.display(description="能力數")
    def capabilities_count(self, obj: Device):
        # 使用預取後的快取避免額外查詢
        return getattr(obj, "_cap_count", None) or obj.capabilities.count()

    @admin.display(description="能力預覽")
    def capabilities_preview(self, obj: Device):
        caps = list(obj.capabilities.all()[:3])
        if not caps:
            return self.empty_value_display
        # 顯示：名稱(kind)
        parts = [f"{c.name}({c.get_kind_display()})" for c in caps]
        suffix = "…" if obj.capabilities.count() > 3 else ""
        return ", ".join(parts) + suffix

    @admin.display(description="IP 位址")
    def ip_address_zh(self, obj: Device):
        return obj.ip_address or "-"

    @admin.display(description="最後心跳")
    def last_ping_zh(self, obj: Device):
        return obj.last_ping

    @admin.display(description="建立時間")
    def created_at_zh(self, obj: Device):
        return obj.created_at


# ========== DeviceCapability 後台（獨立頁） ==========
@admin.register(DeviceCapability)
class DeviceCapabilityAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "kind_zh", "device", "enabled_zh", "order", "slug")
    list_filter = ("kind", "enabled", "device")
    search_fields = ("name", "slug", "device__serial_number", "device__display_name")
    ordering = ("device", "order", "id")

    fieldsets = (
        (None, {"fields": ("device", "enabled", "order")}),
        ("基本資訊", {"fields": ("name", "kind", "slug")}),
        ("設定", {"fields": ("config",)}),
    )

    @admin.display(description="種類")
    def kind_zh(self, obj: DeviceCapability):
        return obj.get_kind_display()

    @admin.display(boolean=True, description="啟用")
    def enabled_zh(self, obj: DeviceCapability):
        return obj.enabled


@admin.register(DeviceCommand)
class DeviceCommandAdmin(admin.ModelAdmin):
    list_display = (
        "device",
        "command_zh",
        "status_zh",
        "req_id",
        "created_at_zh",
        "taken_at",
        "done_at",
        "expires_at",
    )
    list_filter = ("status", "command", "device")
    search_fields = (
        "command",
        "req_id",
        "device__serial_number",
        "device__display_name",
    )
    list_select_related = ("device",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)

    @admin.display(description="指令")
    def command_zh(self, obj: DeviceCommand):
        return obj.command

    @admin.display(description="狀態")
    def status_zh(self, obj: DeviceCommand):
        return obj.status

    @admin.display(description="建立時間")
    def created_at_zh(self, obj: DeviceCommand):
        return obj.created_at


@admin.register(DeviceSchedule)
class DeviceScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "device",
        "action_zh",
        "run_at_zh",
        "status_zh",
        "created_at_zh",
        "done_at",
    )
    list_filter = ("status", "action")
    search_fields = ("action", "device__serial_number", "device__display_name")
    list_select_related = ("device",)
    ordering = ("-run_at",)
    readonly_fields = ("created_at",)

    @admin.display(description="動作")
    def action_zh(self, obj: DeviceSchedule):
        return obj.action

    @admin.display(description="執行時間")
    def run_at_zh(self, obj: DeviceSchedule):
        return obj.run_at

    @admin.display(description="狀態")
    def status_zh(self, obj: DeviceSchedule):
        return obj.status

    @admin.display(description="建立時間")
    def created_at_zh(self, obj: DeviceSchedule):
        return obj.created_at
