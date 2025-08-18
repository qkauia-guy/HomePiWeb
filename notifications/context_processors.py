def notifications_summary(request):
    if not request.user.is_authenticated:
        return {}
    from .models import Notification

    user = request.user
    member_unread = Notification.objects.filter(
        user=user, kind="member", is_read=False
    ).count()
    device_unread = Notification.objects.filter(
        user=user, kind="device", is_read=False
    ).count()
    total_unread = member_unread + device_unread
    latest = Notification.objects.filter(user=user).order_by("-created_at")[:5]
    return {
        "notif_total_unread": total_unread,
        "notif_member_unread": member_unread,
        "notif_device_unread": device_unread,
        "notif_latest": latest,
    }
