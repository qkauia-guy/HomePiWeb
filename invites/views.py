# invites/views.py
from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from groups.models import Group, GroupDevice, GroupMembership
from groups.permissions import is_group_admin  # 權限檢查
from pi_devices.models import Device
from users.forms import InviteRegisterForm, UserRegisterForm  # 若未使用可移除
from .models import Invitation

# 🔔 通知：這三個是本檔會用到的
from notifications.services import (
    notify_invite_created,
    notify_group_device_added,
    notify_member_added,
)
from django.db import transaction, OperationalError
import time


@login_required
def invitation_list(request, group_id):
    """群組的邀請列表（含撤銷動作入口）。只有群組擁有者或群組管理員可看。"""
    group = get_object_or_404(Group, pk=group_id)
    if not is_group_admin(request.user, group):
        raise PermissionDenied("沒有權限檢視此群組的邀請")

    status = request.GET.get("status", "all")  # all / active / used / expired
    qs = (
        Invitation.objects.filter(group=group)
        .select_related("group", "device", "invited_by")
        .order_by("-created_at")
    )

    now = timezone.now()
    if status == "active":
        qs = qs.filter(is_active=True).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=now)
        )
    elif status == "used":
        qs = qs.filter(used_count__gte=1)
    elif status == "expired":
        qs = qs.filter(Q(is_active=False) | Q(expires_at__lte=now))

    return render(
        request,
        "invites/list.html",
        {"group": group, "invites": qs, "status": status, "now": now},
    )


@login_required
@require_http_methods(["POST"])
def revoke_invitation(request, code):
    """撤銷（停用）單一邀請；只允許群組擁有者/群組管理員。"""
    inv = Invitation.objects.select_for_update().select_related("group").get(code=code)
    if not is_group_admin(request.user, inv.group):
        raise PermissionDenied("沒有權限撤銷此邀請")

    if inv.is_active:
        inv.is_active = False
        inv.save(update_fields=["is_active"])
        messages.success(request, "已撤銷邀請")
    else:
        messages.info(request, "此邀請已是停用狀態")

    return redirect(reverse("invite_list", args=[inv.group_id]))


@login_required
def create_invitation(request, group_id, device_id):
    """建立一張邀請（單次使用、預設 7 天）。"""
    group = get_object_or_404(Group, pk=group_id)
    device = get_object_or_404(Device, pk=device_id)

    if not is_group_admin(request.user, group):
        raise PermissionDenied("無權限建立邀請")

    if not group.devices.filter(pk=device.pk).exists():
        return render(request, "invites/error.html", {"message": "此裝置不在群組中"})

    if request.method == "POST":
        role = (request.POST.get("role") or "operator").lower()
        max_uses = 1  # ⭐ 強制單次使用
        days = int(request.POST.get("days") or 7)
        expires_at = timezone.now() + timedelta(days=days)
        email = request.POST.get("email") or None  # 可選：限定信箱

        inv = Invitation.objects.create(
            group=group,
            device=device,
            invited_by=request.user,
            role=role,
            max_uses=max_uses,
            expires_at=expires_at,
            email=email,
        )

        # ✅ 交易提交成功後送出站內通知（知會建立者）
        transaction.on_commit(lambda: notify_invite_created(invitation=inv))

        invite_url = request.build_absolute_uri(f"/invites/accept/{inv.code}/")
        messages.success(request, "邀請已建立")
        return render(
            request, "invites/created.html", {"invite_url": invite_url, "inv": inv}
        )

    return render(request, "invites/create.html", {"group": group, "device": device})


@require_http_methods(["GET", "POST"])
def accept_invite(request, code):
    inv = get_object_or_404(Invitation, code=code)
    if not inv.is_valid():
        return render(request, "invites/invalid.html")

    def _accept_for(user):
        backoffs = (0, 0.05, 0.1, 0.2, 0.4)
        for i, sleep_s in enumerate(backoffs):
            if sleep_s:
                time.sleep(sleep_s)
            try:
                with transaction.atomic():
                    pre_is_member = GroupMembership.objects.filter(
                        group=inv.group, user=user
                    ).exists()
                    pre_has_device = GroupDevice.objects.filter(
                        group=inv.group, device=inv.device
                    ).exists()

                    _join_and_consume(inv, user)  # 交易內只做 DB 寫入

                    def _after_commit():
                        post_is_member = GroupMembership.objects.filter(
                            group=inv.group, user=user
                        ).exists()
                        post_has_device = GroupDevice.objects.filter(
                            group=inv.group, device=inv.device
                        ).exists()

                        if (not pre_is_member) and post_is_member:
                            notify_member_added(
                                actor=user, group=inv.group, member=user, role=inv.role
                            )
                        if inv.device_id and (not pre_has_device) and post_has_device:
                            notify_group_device_added(
                                actor=user, group=inv.group, device=inv.device
                            )

                    transaction.on_commit(_after_commit)

                return render(
                    request,
                    "invites/success.html",
                    {"group": inv.group, "device": inv.device},
                )
            except OperationalError as e:
                if "database is locked" in str(e).lower() and i < len(backoffs) - 1:
                    continue
                raise

    if request.user.is_authenticated:
        return _accept_for(request.user)

    if request.method == "POST":
        if "login" in request.POST:
            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                user = form.get_user()
                resp = _accept_for(user)  # 先提交 DB
                login(request, user)  # 再寫 session
                return resp
            return render(
                request,
                "invites/accept.html",
                {
                    "inv": inv,
                    "login_form": form,
                    "register_form": InviteRegisterForm(fixed_email=inv.email),
                },
            )

        if "register" in request.POST:
            form = InviteRegisterForm(request.POST, fixed_email=inv.email)
            if form.is_valid():
                user = form.save()
                resp = _accept_for(user)  # 先提交 DB
                login(request, user)  # 再寫 session
                return resp
            return render(
                request,
                "invites/accept.html",
                {
                    "inv": inv,
                    "login_form": AuthenticationForm(),
                    "register_form": form,
                },
            )

    return render(
        request,
        "invites/accept.html",
        {
            "inv": inv,
            "login_form": AuthenticationForm(
                initial={"username": inv.email} if inv.email else None
            ),
            "register_form": InviteRegisterForm(fixed_email=inv.email),
        },
    )


@transaction.atomic
def _join_and_consume(inv: Invitation, user):
    """
    - 鎖定 Invitation，避免併發搶同一張 code
    - 驗證限定 email（若有）
    - 加入 GroupMembership（若尚未加入）
    - consume 邏輯：增加使用次數、可能關閉 is_active
    """
    inv = Invitation.objects.select_for_update().select_related("group").get(pk=inv.pk)

    if inv.email and inv.email.lower() != user.email.lower():
        raise PermissionDenied("此邀請僅限特定信箱使用")

    GroupMembership.objects.get_or_create(
        user=user,
        group=inv.group,
        defaults={"role": inv.role or "operator"},
    )

    # 若沒綁 email，消費時把使用者 email 記錄住（方便稽核）
    if not inv.email:
        inv.email = user.email

    # 這裡假設 Invitation.consume() 內會：
    # - 檢查 is_valid()
    # - 增加 used_count
    # - 視 max_uses 及 expires_at 決定 is_active
    inv.consume()
    inv.save(update_fields=["email", "used_count", "is_active"])
