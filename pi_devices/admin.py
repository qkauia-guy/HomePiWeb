from django.contrib import admin
from .models import Device


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("serial_number", "verification_code", "is_bound", "created_at")
    search_fields = ("serial_number", "verification_code")
    list_filter = ("is_bound", "created_at")
    ordering = ("-created_at",)
