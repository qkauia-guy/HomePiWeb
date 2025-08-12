from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist  # ← 必加
from .models import GroupMembership


def is_group_admin(user, group) -> bool:
    if not user.is_authenticated:
        return False
    return (group.owner_id == user.id) or GroupMembership.objects.filter(
        user=user, group=group, role="admin"
    ).exists()


def _is_device_owner(user, device) -> bool:
    if not user.is_authenticated or device is None:
        return False
    try:
        # 反向 OneToOne（device.user）在沒有對應 user 時會拋 RelatedObjectDoesNotExist
        return bool(device.user and device.user.pk == user.pk)
    except ObjectDoesNotExist:
        return False


def can_attach_device_to_group(user, device, group) -> bool:
    """
    1) 必須是該裝置的擁有者
    2) GROUP_ALLOW_MEMBER_ATTACH=False（預設）→ 還需是群組管理者
       True → 只要是該群組成員即可
    """
    if not _is_device_owner(user, device):
        return False

    allow = getattr(settings, "GROUP_ALLOW_MEMBER_ATTACH", False)
    if allow:
        return GroupMembership.objects.filter(user=user, group=group).exists()
    return is_group_admin(user, group)
