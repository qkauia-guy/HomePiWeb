from django.contrib import admin
from .models import Group, GroupMembership, GroupDevice


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "device_count", "member_count", "created_at")
    search_fields = ("name", "owner__email")
    list_select_related = ("owner",)

    def device_count(self, obj):
        return obj.devices.count()

    device_count.short_description = "裝置數"

    def member_count(self, obj):
        return obj.memberships.count()

    member_count.short_description = "成員數"


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "group", "role", "joined_at")
    list_filter = ("role", "group")
    search_fields = ("user__email", "group__name")
    list_select_related = ("user", "group")


@admin.register(GroupDevice)
class GroupDeviceAdmin(admin.ModelAdmin):
    list_display = ("group", "device", "added_by", "added_at", "note")
    search_fields = ("group__name", "device__serial_number", "added_by__email")
    list_select_related = ("group", "device", "added_by")
