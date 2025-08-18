from django.utils import timezone
from .. import events
from .core import (
    _create_notification,
)


def notify_share_request_submitted(*, requester, group, device):
    # 若有群組管理員清單，也可在此一併通知
    if group.owner_id:
        _create_notification(
            user=group.owner,
            kind="member",
            event=events.SHARE_REQUEST_SUBMITTED,
            title=f"{requester.email} 申請分享裝置到群組：{group.name}",
            group=group,
            device=device,
            target=device,
            dedup_key=f"share_req_submitted:{group.id}:{device.id}:{requester.id}",
            meta={"requester": requester.id},
        )


def notify_share_request_approved(*, request):
    _create_notification(
        user=request.requester,
        kind="member",
        event=events.SHARE_REQUEST_APPROVED,
        title=f"你的分享申請已核准（{request.group.name} / {request.device.name()}）",
        group=request.group,
        device=request.device,
        target=request.device,
        dedup_key=f"share_req_approved:{request.id}",
        meta={"reviewed_by": getattr(request.reviewed_by, "id", None)},
    )


def notify_share_request_rejected(*, request):
    _create_notification(
        user=request.requester,
        kind="member",
        event=events.SHARE_REQUEST_REJECTED,
        title=f"你的分享申請被拒絕（{request.group.name} / {request.device.name()}）",
        group=request.group,
        device=request.device,
        target=request.device,
        dedup_key=f"share_req_rejected:{request.id}",
        meta={"reviewed_by": getattr(request.reviewed_by, "id", None)},
    )


# =============================================== 持續性授權 ===============================================
def notify_share_grant_opened(*, actor, group, user, grant, created: bool):
    """
    開通/更新持續性授權：
    - created=True  → 事件 SHARE_GRANT_OPENED；不做 dedup（每次開通都要提醒）
    - created=False → 事件 SHARE_GRANT_UPDATED；以 expires_at 當 key 去重（同一天更新不重發）
    """
    verb = "開通" if created else "更新"
    event = events.SHARE_GRANT_OPENED if created else events.SHARE_GRANT_UPDATED

    if created:
        dedup_key = ""  # 不去重：每次開通都發一則新通知
    else:
        key_part = grant.expires_at.date().isoformat() if grant.expires_at else "none"
        dedup_key = f"share_grant_updated:{group.id}:{user.id}:{key_part}"

    return _create_notification(
        user=user,
        kind="member",
        event=event,
        title=f"已{verb}你在 {group.name} 的分享授權",
        group=group,
        target=group,
        dedup_key=dedup_key,
        meta={
            "by": actor.id,
            "expires_at": (str(grant.expires_at) if grant.expires_at else None),
        },
    )


def notify_share_grant_revoked(*, actor, group, user_id):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.get(pk=user_id)

    # ✅ 當天唯一，隔天再撤銷會再發一則
    dedup_key = f"share_grant_revoked:{group.id}:{user.id}:{timezone.now().date()}"

    return _create_notification(
        user=user,
        kind="member",
        event=events.SHARE_GRANT_REVOKED,
        title=f"你在 {group.name} 的分享授權已關閉",
        group=group,
        target=group,
        dedup_key=dedup_key,
        meta={"by": actor.id},
    )
