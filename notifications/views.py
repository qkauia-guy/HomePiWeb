from __future__ import annotations


from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from .models import Notification
from django.urls import reverse
from .serializers import NotificationSerializer
from urllib.parse import urlencode
from django.utils import timezone
from .serializers import NotificationSerializer
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

ORDERING_ALLOWLIST = {"created_at", "read_at", "id"}


# =========================
#        DRF ViewSet
# =========================
class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,  # 僅允許更新 is_read
    viewsets.GenericViewSet,
):
    """
    /api/notifications/?unread=1&kind=member&event=xxx&group_id=1&device_id=2&valid=1&ordering=-created_at
    支援欄位更新：目前僅允許 is_read（避免外部亂改系統欄位）
    """

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # ✅ 建議：一開始就 select_related，可減少列表序列化時的查詢次數
        qs = Notification.objects.for_user(user).select_related("group", "device")

        # 篩選
        unread = self.request.query_params.get("unread")
        if unread in ("1", "true", "True"):
            qs = qs.unread()

        kind = self.request.query_params.get("kind")
        if kind:
            qs = qs.of_kind(kind)

        event = self.request.query_params.get("event")
        if event:
            qs = qs.of_event(event)

        group_id = self.request.query_params.get("group_id")
        if group_id:
            qs = qs.filter(group_id=group_id)

        device_id = self.request.query_params.get("device_id")
        if device_id:
            qs = qs.filter(device_id=device_id)

        valid = self.request.query_params.get("valid")
        if valid in ("1", "true", "True"):
            qs = qs.valid()

        # 排序（僅允許白名單）
        ordering = self.request.query_params.get("ordering")
        if ordering:
            field = ordering.lstrip("-")
            if field in ORDERING_ALLOWLIST:
                qs = qs.order_by(ordering)
            # ⚠️ 否則忽略客製 ordering，改用 Model.Meta.ordering

        return qs

    def partial_update(self, request, *args, **kwargs):
        """
        僅允許更新 is_read（True/False）
        """
        instance = self.get_object()
        allowed = {"is_read"}
        data = {k: v for k, v in request.data.items() if k in allowed}

        # 僅用 serializer 做資料型別驗證，不直接 serializer.save()
        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)

        # 若設為已讀，填 read_at；若設為未讀，清空 read_at
        is_read = serializer.validated_data.get("is_read", instance.is_read)
        if is_read and not instance.is_read:
            instance.is_read = True
            instance.read_at = timezone.now()
            instance.save(update_fields=["is_read", "read_at"])
        elif not is_read and instance.is_read:
            instance.is_read = False
            instance.read_at = None
            instance.save(update_fields=["is_read", "read_at"])
        # 其它欄位一律不允許變更（避免外部亂改）

        # 重新序列化
        out = self.get_serializer(instance)
        return Response(out.data)

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        """
        POST /api/notifications/{id}/read/
        單筆設為已讀
        """
        n = self.get_object()
        n.mark_read()
        return Response({"status": "ok"})

    @action(detail=False, methods=["post"])
    def read_all(self, request):
        """
        POST /api/notifications/read_all/
        將目前查詢篩選結果（或所有）設為已讀
        - 如需只針對未讀：帶 ?unread=1
        """
        qs = self.get_queryset()
        # ✅ 補上 read_at，避免只有 is_read=True 卻沒有時間戳
        now = timezone.now()
        updated = Notification.objects.filter(
            id__in=qs.values("id"), is_read=False
        ).update(is_read=True, read_at=now)
        return Response({"updated": updated})

    @action(detail=False, methods=["post"])
    def unread_all(self, request):
        """
        POST /api/notifications/unread_all/
        將目前查詢篩選結果（或所有）設為未讀
        """
        qs = self.get_queryset()
        updated = Notification.objects.filter(
            id__in=qs.values("id"), is_read=True
        ).update(is_read=False, read_at=None)
        return Response({"updated": updated})

    @action(detail=False, methods=["post"])
    def purge_expired(self, request):
        """
        POST /api/notifications/purge_expired/
        刪除所有已過期（依目前查詢條件）
        """
        qs = self.get_queryset().filter(expires_at__lt=timezone.now())
        deleted, _ = qs.delete()
        return Response({"deleted": deleted})


# =========================
#         Web 視圖
# =========================
def _build_base_qs(request, exclude=("page",)):
    """
    將目前的 GET 參數轉成 querystring，排除指定 key（預設排除 page）。
    給模板分頁連結使用，確保篩選條件不會丟失。
    """
    params = {
        k: v for k, v in request.GET.items() if k not in exclude and v not in (None, "")
    }
    return urlencode(params)


@login_required
def notifications_list(request):
    """
    /notifications/?unread=1&kind=member&event=xxx&group_id=&device_id=&valid=1&page=1
    與 API 的篩選行為一致，並提供模板需要的 kind / base_qs。
    """
    qs = Notification.objects.for_user(request.user)

    # ---- 篩選條件（與 API 對齊）----
    unread = request.GET.get("unread")
    if unread in ("1", "true", "True"):
        qs = qs.unread()

    kind = request.GET.get("kind") or ""  # 給模板高亮使用
    if kind:
        qs = qs.of_kind(kind)

    event = request.GET.get("event")
    if event:
        qs = qs.of_event(event)

    group_id = request.GET.get("group_id")
    if group_id:
        qs = qs.filter(group_id=group_id)

    device_id = request.GET.get("device_id")
    if device_id:
        qs = qs.filter(device_id=device_id)

    valid = request.GET.get("valid")
    if valid in ("1", "true", "True"):
        qs = qs.valid()

    # ---- 分頁 ----
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page") or 1)

    # ---- 給模板的其他參數 ----
    base_qs = _build_base_qs(request)  # 盡量保留目前篩選條件

    return render(
        request,
        "notifications/list.html",
        {
            "page": page,
            "paginator": paginator,
            "kind": kind,  # 供你上方 tab 高亮用
            "base_qs": base_qs,  # 供分頁連結拼接
        },
    )


@login_required
def notifications_read_all(request):
    """
    將使用者所有未讀設為已讀（不看篩選條件）
    """
    if request.method == "POST":
        updated = Notification.mark_all_for_user(request.user, read=True)
        messages.success(request, f"已將 {updated} 則通知標記為已讀")
    return redirect("notifications_list")


@login_required
def notification_read(request, pk: int):
    """
    單筆設為已讀
    """
    if request.method == "POST":
        n = get_object_or_404(Notification.objects.for_user(request.user), pk=pk)
        n.mark_read()  #  同步更新 read_at
        messages.success(request, "已標記為已讀")
    return redirect("notifications_list")


def _event_redirect_url(n: Notification) -> str | None:
    ev = (n.event or "").lower()

    # --- 成員/群組類 ---
    if ev in {
        "group_created",
        "group_renamed",
        "member_added",
        "member_joined",
        "share_grant_opened",
        "share_grant_updated",
        "share_grant_revoked",
        "share_request_submitted",
        "share_request_approved",
        "share_request_rejected",
        "group_device_added",
        "group_device_removed",
        "group_device_renamed",
        "user_online",
        "user_offline",
    }:
        if n.group_id:
            return reverse("group_detail", args=[n.group_id])
        # group_deleted 沒 group 可去時，回首頁
        if ev == "group_deleted":
            return reverse("home")

    if ev == "invite_created":
        # 你有邀請列表頁就導過去，沒有的話導群組頁
        if n.group_id:
            try:
                return reverse("invite_list", args=[n.group_id])
            except Exception:
                return reverse("group_detail", args=[n.group_id])
        return reverse("home")

    if ev == "member_removed":
        # 被移出群組，回首頁
        return reverse("home")

    # --- 裝置類 ---
    if ev in {"device_bound", "device_unbound", "device_renamed", "device_ip_changed"}:
        # 你有裝置詳情頁可換成 'device_detail'；沒有就回主頁
        return reverse("home")

    # 預設：若通知帶 group，導群組；若有 device 但沒群組，導我的裝置
    if n.group_id:
        return reverse("group_detail", args=[n.group_id])
    if n.device_id:
        return reverse("home")

    # 若有 target 指到群組或裝置也可兜
    try:
        if n.target:
            m = n.target_content_type.model
            if m in ("group", "groups.group"):
                return reverse("group_detail", args=[n.target.pk])
            if m in ("device", "pi_devices.device"):
                return reverse("home")
    except Exception:
        pass

    return None


@login_required
def notification_go(request, pk: int):
    """點通知 → 決定導向頁面，並在導向前標記已讀。"""
    n = get_object_or_404(Notification, pk=pk, user=request.user)

    # 標記已讀（避免回跳後仍顯示粗體）
    if not n.is_read:
        n.mark_read()

    url = _event_redirect_url(n)
    if url:
        # 清理 URL 中的 hash 片段（如 #sideBar）
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ''))
        return redirect(clean_url)

    messages.info(request, "找不到對應的詳細頁，已將通知標記為已讀。")
    return redirect("notifications_list")  # 你的通知列表頁路由名
