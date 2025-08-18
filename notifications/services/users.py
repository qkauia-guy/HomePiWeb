from __future__ import annotations
from django.utils import timezone
from .. import events
from .core import _create_notification


def _presence_recipients_for(user):
    """
    找出要接收『user 上/下線』通知的人：
    - user 擁有的群組 owner 自己（除了 user 本人）
    - user 所在的每個群組的 owner 與所有成員（排除 user 本人）
    回傳：[(group, recipient_user), ...]
    """
    from groups.models import Group

    pairs = []

    # 擁有的群組
    owned = Group.objects.filter(owner_id=user.id).select_related("owner")
    for g in owned:
        if g.owner_id and g.owner_id != user.id:
            pairs.append((g, g.owner))

    # 以成員身分所在的群組
    member_groups = (
        Group.objects.filter(memberships__user=user)
        .select_related("owner")
        .prefetch_related("memberships__user")
        .distinct()
    )
    for g in member_groups:
        # owner
        if g.owner_id and g.owner_id != user.id:
            pairs.append((g, g.owner))
        # 成員們
        for ms in g.memberships.all():
            u = getattr(ms, "user", None)
            if u and u.id != user.id:
                pairs.append((g, u))

    # 去重（同一 group-recipient 只保留一次）
    uniq = {}
    for g, u in pairs:
        uniq[(g.id, u.id)] = (g, u)
    return list(uniq.values())


def notify_user_online(*, user):
    """
    『某使用者已上線』：廣播給該使用者所在群組的 owner/成員（排除本人）。
    為避免洗版：對每個收件人 & 群組 & 使用者，每天只發一則。
    """
    today = timezone.now().date()
    for group, recipient in _presence_recipients_for(user):
        _create_notification(
            user=recipient,
            kind="member",
            event=events.USER_ONLINE,
            title=f"{user.email} 已上線（{group.name}）",
            group=group,
            target=group,  # 點通知回群組頁最合理
            dedup_key=f"user_online:{group.id}:{user.id}:{today}",
            meta={"subject_user": user.id},
        )


def notify_user_offline(*, user):
    """
    『某使用者已離線』：同上。通常由排程掃描觸發（見下方 management command）。
    一樣以「每天一則」去重。
    """
    today = timezone.now().date()
    for group, recipient in _presence_recipients_for(user):
        _create_notification(
            user=recipient,
            kind="member",
            event=events.USER_OFFLINE,
            title=f"{user.email} 已離線（{group.name}）",
            group=group,
            target=group,
            dedup_key=f"user_offline:{group.id}:{user.id}:{today}",
            meta={"subject_user": user.id},
        )


def notify_password_changed(
    *, user, actor=None, ip: str | None = None, user_agent: str | None = None
):
    """
    使用者密碼變更成功 → 發一則通知給本人。
    每位使用者每天最多一則（避免連點洗版）。
    """
    today = timezone.now().date()
    return _create_notification(
        user=user,
        kind="member",
        event=events.PASSWORD_CHANGED,
        title="你的密碼已更新",
        body="若非你本人操作，請盡快聯絡管理員並更新帳號安全設定。",
        dedup_key=f"password_changed:{user.id}:{today}",
        meta={
            "by": getattr(actor, "id", None),
            "ip": ip,
            "ua": user_agent[:200] if user_agent else None,  # 控一下長度
        },
    )
