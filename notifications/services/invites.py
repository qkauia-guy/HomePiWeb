from __future__ import annotations
from django.utils import timezone
from django.contrib.auth import get_user_model
from .. import events
from .core import (
    _create_notification,
)

# ================================================ 群組 / 邀請 ================================================


def notify_invite_created(*, invitation):
    _create_notification(
        user=invitation.invited_by,
        kind="member",
        event=events.INVITE_CREATED,
        title=f"已建立邀請碼：{invitation.group.name} / {invitation.device.serial_number}",
        group=invitation.group,
        device=invitation.device,
        target=invitation,
        dedup_key=f"invite_created:{invitation.id}",
    )
