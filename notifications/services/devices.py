from django.utils import timezone
from django.contrib.auth import get_user_model
from .. import events
from .core import (
    _create_notification,
    _bulk_create_notifications,
    _user_label,
)


def notify_device_bound(*, device, owner, actor=None):
    return _create_notification(
        user=owner,
        kind="device",
        event=events.DEVICE_BOUND,
        title=f"已綁定裝置：{device.name()}",
        device=device,
        target=device,
        # 加入日期，避免被舊通知吃掉
        dedup_key=f"device_bound:{device.id}:{owner.id}:{timezone.now().date()}",
        meta={"by": getattr(actor, "id", None)},
    )


def notify_device_unbound(*, device, owner, actor=None):
    # owner 是「解綁前」的擁有者
    return _create_notification(
        user=owner,
        kind="device",
        event=events.DEVICE_UNBOUND,
        title=f"裝置已解除綁定：{device.name()}",
        device=device,
        target=device,
        dedup_key=f"device_unbound:{device.id}:{owner.id}:{timezone.now().date()}",
        meta={"by": getattr(actor, "id", None)},
    )


def notify_device_renamed(*, device, owner, old_name, new_name, actor=None):
    return _create_notification(
        user=owner,
        kind="device",
        event=events.DEVICE_RENAMED,
        title=f"裝置更名：{old_name or '（未命名）'} → {new_name or '（未命名）'}",
        device=device,
        target=device,
        # ✅ 含日期，避免被「以前同名」的舊通知吃掉；同一天同名不洗版
        dedup_key=f"device_renamed:{device.id}:{owner.id}:{(new_name or '').strip()}:{timezone.now().date()}",
        meta={"by": getattr(actor, "id", None), "old": old_name, "new": new_name},
    )


def notify_device_ip_changed(*, device, owner, old_ip, new_ip):
    return _create_notification(
        user=owner,
        kind="device",
        event=events.DEVICE_IP_CHANGED,
        title=f"裝置 IP 變更：{old_ip or '未知'} → {new_ip}",
        device=device,
        target=device,
        # 每天同一新 IP 只發一次
        dedup_key=f"device_ip_changed:{device.id}:{owner.id}:{new_ip}:{timezone.now().date()}",
        meta={"old_ip": old_ip, "new_ip": new_ip},
    )


# ===============================
# 裝置操作通知
# ===============================

def notify_device_action(*, device, action, actor, group=None, capability_name=None):
    """
    裝置操作通知：發送給群組所有成員（如果指定群組）或裝置擁有者
    
    Args:
        device: 裝置物件
        action: 操作類型 (如 'light_on', 'locker_unlock' 等)
        actor: 操作者
        group: 群組物件（可選，如果提供則發送給群組成員）
        capability_name: 能力名稱（如 '客廳燈', '大門鎖' 等）
    """
    # 取得操作者標籤
    actor_label = _user_label(actor)
    
    # 取得裝置名稱
    try:
        device_name = device.name() if callable(getattr(device, "name", None)) else (getattr(device, "name", "") or "未命名裝置")
    except Exception:
        device_name = "未命名裝置"
    
    # 取得能力名稱
    cap_name = capability_name or "裝置"
    
    # 根據操作類型決定事件和標題
    event_map = {
        "light_on": (events.DEVICE_LIGHT_ON, f"{actor_label} 開啟了 {device_name} 的 {cap_name}"),
        "light_off": (events.DEVICE_LIGHT_OFF, f"{actor_label} 關閉了 {device_name} 的 {cap_name}"),
        "light_toggle": (events.DEVICE_LIGHT_TOGGLE, f"{actor_label} 切換了 {device_name} 的 {cap_name}"),
        "locker_lock": (events.DEVICE_LOCKER_LOCK, f"{actor_label} 鎖定了 {device_name} 的 {cap_name}"),
        "locker_unlock": (events.DEVICE_LOCKER_UNLOCK, f"{actor_label} 解鎖了 {device_name} 的 {cap_name}"),
        "locker_toggle": (events.DEVICE_LOCKER_TOGGLE, f"{actor_label} 切換了 {device_name} 的 {cap_name}"),
        "auto_light_on": (events.DEVICE_AUTO_LIGHT_ON, f"{actor_label} 啟用了 {device_name} 的 {cap_name} 自動模式"),
        "auto_light_off": (events.DEVICE_AUTO_LIGHT_OFF, f"{actor_label} 停用了 {device_name} 的 {cap_name} 自動模式"),
        "auto_lock_on": (events.DEVICE_AUTO_LOCK_ON, f"{actor_label} 啟用了 {device_name} 的 {cap_name} 自動上鎖"),
        "auto_lock_off": (events.DEVICE_AUTO_LOCK_OFF, f"{actor_label} 停用了 {device_name} 的 {cap_name} 自動上鎖"),
    }
    
    event, title = event_map.get(action, (f"device_{action}", f"{actor_label} 操作了 {device_name} 的 {cap_name}"))
    
    # 決定收件人
    recipients = []
    
    if group:
        # 發送給群組所有成員（包含 owner）
        User = get_user_model()
        recipient_ids = set(group.memberships.values_list("user_id", flat=True))
        if group.owner_id:
            recipient_ids.add(group.owner_id)
        
        # 排除操作者本人
        if getattr(actor, "id", None) in recipient_ids:
            recipient_ids.discard(actor.id)
        
        recipients = list(User.objects.filter(id__in=recipient_ids))
    else:
        # 只發送給裝置擁有者（如果不是操作者本人）
        owner = getattr(device, "user", None)
        if owner and owner.id != getattr(actor, "id", None):
            recipients = [owner]
    
    if not recipients:
        return []
    
    # 建立通知 payloads
    payloads = []
    today = timezone.now().date()
    
    for user in recipients:
        payloads.append({
            "user": user,
            "dedup_key": f"device_action:{device.id}:{action}:{user.id}:{today}",
            "meta": {
                "by": getattr(actor, "id", None),
                "by_email": getattr(actor, "email", None),
                "by_name": actor_label,
                "action": action,
                "capability_name": cap_name,
            },
        })
    
    # 批次建立通知
    return _bulk_create_notifications(
        user_payloads=payloads,
        kind="device",
        event=event,
        title=title,
        target=device,
        group=group,
        device=device,
    )
