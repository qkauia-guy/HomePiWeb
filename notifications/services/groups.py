from __future__ import annotations
from django.utils import timezone
from django.contrib.auth import get_user_model

from .. import events
from .core import (
    _create_notification,
    _bulk_create_notifications,
    _user_label,
)


def notify_group_created(*, group, actor=None) -> Notification:
    """
    群組建立成功後通知建立者（owner）。
    建議在呼叫端使用 transaction.on_commit(...) 以確保狀態已提交。
    """
    return _create_notification(
        user=group.owner,
        kind="member",
        event=events.GROUP_CREATED,
        title=f"群組已建立：{group.name}",
        group=group,
        target=group,
        dedup_key=f"group_created:{group.id}",
        meta={"by": getattr(actor, "id", None)},
    )


def notify_group_renamed(*, group, old_name: str, new_name: str, actor):
    """
    群組改名：通知群組所有成員（含 owner），排除操作者本人。
    使用批次建立以提升效能。
    """
    recipients = set()
    if group.owner_id:
        recipients.add(group.owner)
    for ms in group.memberships.select_related("user").all():
        if ms.user_id:
            recipients.add(ms.user)

    # 排除操作者
    recipients = [u for u in recipients if u and u.id != getattr(actor, "id", None)]
    if not recipients:
        return

    payloads = []
    for u in recipients:
        payloads.append(
            {
                "user": u,
                "dedup_key": f"group_renamed:{group.id}:{u.id}:{new_name}",
                "meta": {
                    "by": getattr(actor, "id", None),
                    "old_name": old_name,
                    "new_name": new_name,
                },
            }
        )

    _bulk_create_notifications(
        user_payloads=payloads,
        kind="member",
        event=events.GROUP_RENAMED,
        title=f"群組已更名：{old_name} → {new_name}",
        target=group,
        group=group,
    )


def notify_group_deleted(*, user, group_name: str, group_id: int | None, actor=None):
    """
    群組被刪除：通知該群組的成員（不含操作者本人）。
    不指向 target/group（因已刪除），資訊放在 title/meta。
    """
    return _create_notification(
        user=user,
        kind="member",
        event=events.GROUP_DELETED,
        title=f"群組已刪除：{group_name}",
        body="此群組已被擁有者刪除，相關裝置與權限已解除。",
        dedup_key=f"group_deleted:{group_id or group_name}:{user.id}",
        meta={
            "group_id": group_id,
            "group_name": group_name,
            "by": getattr(actor, "id", None),
        },
    )


# member


def notify_member_added(*, actor, group, member, role: str):
    """
    新成員加入群組：
    - 發給新成員本人（member_added）
    - 廣播給群組中其他成員與 owner（member_joined），排除操作者與新成員
    """
    # 1) 新成員本人
    _create_notification(
        user=member,
        kind="member",
        event=events.MEMBER_ADDED,
        title=f"你已加入群組：{group.name}",
        group=group,
        target=group,
        dedup_key=f"group:{group.id}:member_added:self:{member.id}",
        meta={"by": getattr(actor, "id", None), "role": role},
    )

    # 2) 其他成員 + owner（排除新成員與操作者）
    recipient_ids = set(
        group.memberships.exclude(user_id=member.id).values_list("user_id", flat=True)
    )
    if group.owner_id:
        recipient_ids.add(group.owner_id)
    if getattr(actor, "id", None) in recipient_ids:
        recipient_ids.remove(actor.id)

    if not recipient_ids:
        return

    User = get_user_model()
    recipients = list(User.objects.filter(id__in=recipient_ids))

    payloads = []
    for u in recipients:
        payloads.append(
            {
                "user": u,
                "dedup_key": f"group:{group.id}:member_joined:{member.id}:{u.id}",
                "meta": {
                    "by": getattr(actor, "id", None),
                    "member": member.id,
                    "role": role,
                },
            }
        )

    _bulk_create_notifications(
        user_payloads=payloads,
        kind="member",
        event=events.MEMBER_JOINED,
        title=f"{member.email} 加入群組：{group.name}",
        target=group,
        group=group,
    )


def notify_member_role_changed(*, actor, group, member, old_role, new_role):
    _create_notification(
        user=member,
        kind="member",
        event=events.MEMBER_ROLE_CHANGED,
        title=f"你在群組 {group.name} 的角色變更：{old_role} → {new_role}",
        group=group,
        target=group,
        dedup_key=f"group:{group.id}:role_change:{member.id}:{new_role}",
        meta={"by": actor.id, "old": old_role, "new": new_role},
    )


def notify_member_removed(*, actor, group, member):
    _create_notification(
        user=member,
        kind="member",
        event=events.MEMBER_REMOVED,
        title=f"你已被移出群組：{group.name}",
        group=group,
        target=group,
        dedup_key=f"group:{group.id}:member_removed:{member.id}",
        meta={"by": actor.id},
    )


def notify_group_device_added(*, actor, group, device, include_actor: bool = True):
    """
    群組加入裝置：廣播給群組 owner、所有成員，以及裝置擁有者（若存在）。
    - include_actor=False 可排除操作者本人
    - 去重：同一天、同收件人、同 group/device 僅一則
    """
    User = get_user_model()
    recipient_ids = set(group.memberships.values_list("user_id", flat=True))
    if group.owner_id:
        recipient_ids.add(group.owner_id)
    owner_id = getattr(device, "user_id", None)
    if owner_id:
        recipient_ids.add(owner_id)

    if not include_actor and getattr(actor, "id", None) in recipient_ids:
        recipient_ids.discard(actor.id)
    if not recipient_ids:
        return

    recipients = list(User.objects.filter(id__in=recipient_ids))

    # 安全取得裝置名稱
    try:
        dev_name = (
            device.name()
            if callable(getattr(device, "name", None))
            else (getattr(device, "name", "") or "（未命名）")
        )
    except Exception:
        dev_name = "（未命名）"

    actor_label = _user_label(actor)
    bucket = timezone.now().strftime("%Y%m%d%H")

    for u in recipients:
        is_device_owner = owner_id is not None and u.id == owner_id
        kind = "device" if is_device_owner else "member"
        title = (
            f"{actor_label} 已將你的裝置加入群組：{group.name}"
            if is_device_owner
            else f"{actor_label} 在群組 {group.name} 加入裝置：{dev_name}"
        )

        _create_notification(
            user=u,
            kind=kind,
            event=events.GROUP_DEVICE_ADDED,
            title=title,
            group=group,
            device=device,
            target=device,
            dedup_key=f"group_device_added:{group.id}:{getattr(device, 'id', 'NA')}:{u.id}:{bucket}",
            meta={
                "by": getattr(actor, "id", None),
                "by_email": getattr(actor, "email", None),
                "by_name": actor_label,
            },
        )


def notify_group_device_removed(
    *, actor, group, device, include_actor: bool = True, device_owner=None
):
    """
    群組移除裝置 → 廣播給：
      - 群主
      - 全體群組成員
      - 裝置擁有者（若提供 device_owner，優先；否則用 device.user）
    標題會顯示『是誰移除的』。
    每位收件人每天一則（依 group+device+recipient 去重）。
    """
    User = get_user_model()

    # 收件人（id 集合）
    recipient_ids = set(group.memberships.values_list("user_id", flat=True))
    if group.owner_id:
        recipient_ids.add(group.owner_id)

    owner = device_owner or getattr(device, "user", None)
    owner_id = getattr(owner, "id", None)
    if owner_id:
        recipient_ids.add(owner_id)

    if not include_actor and getattr(actor, "id", None) in recipient_ids:
        recipient_ids.discard(actor.id)
    if not recipient_ids:
        return

    recipients = list(User.objects.filter(id__in=recipient_ids))

    # 安全取得裝置名稱
    try:
        dev_name = (
            device.name()
            if callable(getattr(device, "name", None))
            else (getattr(device, "name", "") or "（未命名）")
        )
    except Exception:
        dev_name = "（未命名）"

    actor_label = _user_label(actor)
    today = timezone.now().date()

    for u in recipients:
        is_device_owner = owner_id is not None and u.id == owner_id
        kind = "device" if is_device_owner else "member"
        # ★ 標題含操作者
        title = (
            f"{actor_label} 將你的裝置自群組 {group.name} 移除"
            if is_device_owner
            else f"{actor_label} 移除了群組 {group.name} 的裝置：{dev_name}"
        )

        _create_notification(
            user=u,
            kind=kind,
            event=events.GROUP_DEVICE_REMOVED,
            title=title,
            group=group,
            device=device,
            target=device,
            dedup_key=f"group_device_removed:{group.id}:{getattr(device, 'id', 'NA')}:{u.id}:{today}",
            meta={
                "by": getattr(actor, "id", None),
                "by_email": getattr(actor, "email", None),
                "by_name": actor_label,
            },
        )


def notify_group_device_renamed(*, actor, group, device, old_name: str, new_name: str):
    """
    裝置在某群組中被改名：廣播給群組 owner + 成員（排除操作者本人）
    dedup：同一天、同收件人、同 group/device/new_name 僅一則，避免洗版
    """
    recipients = set()
    if group.owner_id:
        recipients.add(group.owner)
    for ms in group.memberships.select_related("user").all():
        if ms.user_id:
            recipients.add(ms.user)

    recipients = [u for u in recipients if u and u.id != getattr(actor, "id", None)]

    title = f"群組 {group.name} 的裝置更名：{old_name or '（未命名）'} → {new_name or '（未命名）'}"
    today = timezone.now().date()
    for u in recipients:
        _create_notification(
            user=u,
            kind="member",
            event=events.GROUP_DEVICE_RENAMED,
            title=title,
            group=group,
            device=device,
            target=device,
            dedup_key=f"group_device_renamed:{group.id}:{device.id}:{u.id}:{(new_name or '').strip()}:{today}",
            meta={"by": getattr(actor, "id", None), "old": old_name, "new": new_name},
        )
