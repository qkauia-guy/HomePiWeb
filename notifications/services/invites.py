# notifications/services/invites.py
from __future__ import annotations
from django.utils import timezone
from django.contrib.auth import get_user_model
from .. import events
from .core import _create_notification


def _device_title(inv):
    """
    回傳用在通知標題的裝置描述：
    - 單裝置：顯示 display_name 或 serial_number
    - 多裝置（有 InvitationDevice 明細）：顯示「N 台裝置」
    - 無裝置：顯示「無特定裝置」
    """
    # 單裝置
    if getattr(inv, "device_id", None):
        d = inv.device
        if d:
            return (
                getattr(d, "display_name", None)
                or getattr(d, "serial_number", "")
                or "裝置"
            )

    # 多裝置（依你的 related_name 調整；這裡假設是 device_items）
    items_rel = getattr(inv, "device_items", None)
    if items_rel is not None:
        try:
            cnt = items_rel.count()
        except Exception:
            cnt = 0
        if cnt > 0:
            return f"{cnt} 台裝置"

    # 都沒有
    return "無特定裝置"


def notify_invite_created(*, invitation):
    device_title = _device_title(invitation)

    _create_notification(
        user=invitation.invited_by,  # 或者你要通知 group.owner 也行
        kind="member",
        event=events.INVITE_CREATED,
        title=f"已建立邀請碼：{invitation.group.name} / {device_title}",
        group=invitation.group,
        device=getattr(invitation, "device", None),  # 允許 None
        target=invitation,
        dedup_key=f"invite_created:{invitation.id}",
    )
