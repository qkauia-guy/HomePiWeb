from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from .models import GroupMembership, GroupShareGrant, GroupDevice


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


def can_detach_device_from_group(user, device, group) -> bool:
    # 管理員（含群主）可移除任何裝置
    from .permissions import is_group_admin

    if is_group_admin(user, group):
        return True

    # 只有當初把裝置掛入的人可以移除
    try:
        gd = GroupDevice.objects.select_related("added_by").get(
            group=group, device=device
        )
    except GroupDevice.DoesNotExist:
        return False  # 不在群組裡就不用談移除

    # 早期資料可能 added_by = NULL：這種情況下只有管理員能移除（上面已處理）
    if gd.added_by is None:
        return False

    return gd.added_by_id == user.id


def _is_group_member(user, group) -> bool:
    if not user.is_authenticated or not group:
        return False
    if getattr(group, "owner_id", None) == user.id:
        return True
    return GroupMembership.objects.filter(user=user, group=group).exists()


def _is_device_owner(user, device) -> bool:
    if not user.is_authenticated or not device:
        return False
    return getattr(device, "user_id", None) == user.id


def has_active_share_grant(user, group) -> bool:
    return GroupShareGrant.objects.filter(
        user=user, group=group, is_active=True
    ).exists()


def can_attach_device_to_group(user, device, group) -> bool:
    """
    新規則：
    - 群組管理員（含 owner）→ 直接可加裝置
    - 一般成員 → 需同時符合：
        a) 是該裝置擁有者
        b) 是該群組成員
        c) 擁有在該群組的有效分享授權（GroupShareGrant）
    """
    from .permissions import is_group_admin  # 你既有函式

    if is_group_admin(user, group):
        return True

    return (
        _is_device_owner(user, device)
        and _is_group_member(user, group)
        and has_active_share_grant(user, group)
    )
