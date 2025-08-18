from __future__ import annotations
from typing import Iterable, Optional, Dict, Any, List
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from ..models import Notification


# ===============================
# 低階小工具：建立單筆通知（含去重）
# ===============================
def _create_notification(
    *,
    user,
    kind: str,
    event: str,
    title: str,
    body: str = "",
    target=None,
    group=None,
    device=None,
    dedup_key: str = "",
    meta: Optional[Dict[str, Any]] = None,
    expires_at=None,
) -> Notification:
    """
    建立單筆通知。
    - 若提供 dedup_key，且同一 user 已存在相同 dedup_key 紀錄 → 直接回傳舊紀錄（避免重複）
    - target 可是任意模型物件（GenericForeignKey）
    """
    if dedup_key:
        existing = Notification.objects.filter(user=user, dedup_key=dedup_key).first()
        if existing:
            return existing

    n = Notification(
        user=user,
        kind=kind,
        event=event,
        title=title,
        body=body,
        group=group,
        device=device,
        dedup_key=dedup_key or "",
        meta=meta or {},
        expires_at=expires_at,
    )

    if target is not None:
        n.target_content_type = ContentType.objects.get_for_model(target)
        n.target_object_id = str(getattr(target, "pk", target))

    n.save()
    return n


# ===================================
# 低階小工具：多人批次建立（含去重）
# ===================================
def _bulk_create_notifications(
    *,
    user_payloads: Iterable[Dict[str, Any]],
    kind: str,
    event: str,
    title: str,
    body: str = "",
    target=None,
    group=None,
    device=None,
    default_meta: Optional[Dict[str, Any]] = None,
    expires_at=None,
) -> List[Notification]:
    """
    多人廣播用：
    - user_payloads 例：
      [
        {"user": u1, "dedup_key": "abc", "meta": {"x": 1}},
        {"user": u2, "dedup_key": "", "meta": None},
      ]
    - 自動對 (user, dedup_key) 去重（有 key 且舊資料存在就跳過）
    """
    default_meta = default_meta or {}

    # 準備 target 之 content type / object id
    target_ct = None
    target_oid = None
    if target is not None:
        target_ct = ContentType.objects.get_for_model(target)
        target_oid = str(getattr(target, "pk", target))

    # 先查已有的 (user, dedup_key)
    dedup_pairs = [
        (p["user"].id, p.get("dedup_key") or "")
        for p in user_payloads
        if p.get("dedup_key")
    ]
    existing_pairs = set()
    if dedup_pairs:
        users = [uid for uid, _ in dedup_pairs]
        keys = list(set([dk for _, dk in dedup_pairs]))
        existing_qs = Notification.objects.filter(
            user_id__in=users,
            dedup_key__in=keys,
        ).only("user_id", "dedup_key")
        existing_pairs = set((n.user_id, n.dedup_key) for n in existing_qs)

    to_create: List[Notification] = []
    for p in user_payloads:
        u = p["user"]
        dk = (p.get("dedup_key") or "").strip()
        merged_meta = {**default_meta, **(p.get("meta") or {})}

        # 有 dedup_key 且已存在 → 跳過
        if dk and (u.id, dk) in existing_pairs:
            continue

        n = Notification(
            user=u,
            kind=kind,
            event=event,
            title=title,
            body=body,
            group=group,
            device=device,
            dedup_key=dk,
            meta=merged_meta,
            expires_at=expires_at,
        )
        if target_ct:
            n.target_content_type = target_ct
            n.target_object_id = target_oid
        to_create.append(n)

    if not to_create:
        return []

    Notification.objects.bulk_create(to_create, batch_size=500)
    return to_create


# ==========================================「操作者」直接寫進通知標題 ===========================================


def _user_label(u) -> str:
    """顯示操作者名稱：優先全名，其次 email，最後 '系統'。"""
    if not u:
        return "系統"
    if hasattr(u, "get_full_name"):
        name = (u.get_full_name() or "").strip()
        if name:
            return name
    # 你也可以改成 u.username
    return getattr(u, "email", None) or "系統"
