def notifications_summary(request):
    if not request.user.is_authenticated:
        return {}
    from .models import Notification

    user = request.user
    # 修正：只計算有效的未讀通知
    member_unread = Notification.objects.filter(
        user=user, kind="member", is_read=False
    ).valid().count()
    device_unread = Notification.objects.filter(
        user=user, kind="device", is_read=False
    ).valid().count()
    total_unread = member_unread + device_unread
    # 修正：只顯示有效的通知
    latest = Notification.objects.filter(user=user).valid().order_by("-created_at")[:5]
    return {
        "notif_total_unread": total_unread,
        "notif_member_unread": member_unread,
        "notif_device_unread": device_unread,
        "notif_latest": latest,
    }
