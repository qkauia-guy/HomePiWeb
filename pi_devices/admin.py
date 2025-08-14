# admin.py
from django.contrib import admin
from django.utils import timezone
from datetime import timedelta
from .models import Device
from django.urls import reverse
from django.utils.html import format_html
from django.db import models


ONLINE_WINDOW_SECONDS = 60  # settings 可配置


class OnlineStatusFilter(admin.SimpleListFilter):
    title = "在線狀態"
    parameter_name = "online"

    def lookups(self, request, model_admin):
        return (
            ("1", "在線"),
            ("0", "離線"),
        )

    def queryset(self, request, queryset):
        if self.value() == "1":
            return queryset.filter(
                last_ping__gte=timezone.now() - timedelta(seconds=ONLINE_WINDOW_SECONDS)
            )
        if self.value() == "0":
            return queryset.filter(
                models.Q(last_ping__isnull=True)
                | models.Q(
                    last_ping__lt=timezone.now()
                    - timedelta(seconds=ONLINE_WINDOW_SECONDS)
                )
            )
        return queryset


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "serial_number",
        "verification_code",
        "is_bound",
        "created_at",
        "owner_link",
        "online",
        "ip_address",
        "last_ping",
        "groups_count",
    )
    list_select_related = ("user",)
    search_fields = (
        "serial_number",
        "verification_code",
        "token",
        "user__email",
        "display_name",
    )
    list_filter = ("is_bound", "created_at", OnlineStatusFilter)
    ordering = ("-created_at",)
    empty_value_display = "-"
    readonly_fields = (
        "serial_number",
        "verification_code",
        "token",
        "created_at",
        "last_ping",
    )

    @admin.display(description="擁有者", ordering="user__email")
    def owner_link(self, obj):
        if getattr(obj, "user", None):
            url = reverse("admin:users_user_change", args=[obj.user.pk])
            return format_html('<a href="{}">{}</a>', url, obj.user.email)
        return self.empty_value_display

    @admin.display(boolean=True, description="在線", ordering="last_ping")
    def online(self, obj):
        return obj.is_online()

    @admin.display(description="群組數")
    def groups_count(self, obj):
        return obj.groups.count()
