from django.utils import timezone
from .. import events
from .core import (
    _create_notification,
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
