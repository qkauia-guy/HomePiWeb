# notifications/services/__init__.py
from .core import _create_notification, _bulk_create_notifications, _user_label
from .groups import (
    notify_group_created,
    notify_group_deleted,
    notify_group_renamed,
    notify_member_added,
    notify_member_removed,
    notify_member_left,
    notify_member_role_changed,
    notify_group_device_added,
    notify_group_device_removed,
    notify_group_device_renamed,
)
from .devices import (
    notify_device_bound,
    notify_device_unbound,
    notify_device_renamed,
    notify_device_ip_changed,
)
from .shares import (
    notify_share_request_submitted,
    notify_share_request_approved,
    notify_share_request_rejected,
    notify_share_grant_opened,
    notify_share_grant_revoked,
)
from .users import notify_user_online, notify_user_offline, notify_password_changed
from .invites import notify_invite_created

__all__ = [
    # core
    "_create_notification",
    "_bulk_create_notifications",
    "_user_label",
    # groups
    "notify_group_created",
    "notify_group_deleted",
    "notify_group_renamed",
    "notify_member_added",
    "notify_member_removed",
    "notify_member_left",
    "notify_member_role_changed",
    "notify_group_device_added",
    "notify_group_device_removed",
    "notify_group_device_renamed",
    # devices
    "notify_device_bound",
    "notify_device_unbound",
    "notify_device_renamed",
    "notify_device_ip_changed",
    # shares
    "notify_share_request_submitted",
    "notify_share_request_approved",
    "notify_share_request_rejected",
    "notify_share_grant_opened",
    "notify_share_grant_revoked",
    # users
    "notify_user_online",
    "notify_user_offline",
    "notify_password_changed",
    # invites
    "notify_invite_created",
]
