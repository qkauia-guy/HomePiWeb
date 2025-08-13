from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from datetime import timedelta

from groups.models import Group, GroupMembership
from groups.permissions import is_group_admin  # ← 換成 permissions
from pi_devices.models import Device
from users.forms import UserRegisterForm
from .models import Invitation
from django.db.models import Q
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from users.forms import InviteRegisterForm


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
@transaction.atomic
def revoke_invitation(request, code):
    """撤銷（停用）單一邀請；只允許群組擁有者/群組管理員。"""
    # 鎖定這筆邀請以避免併發與 race condition
    inv = Invitation.objects.select_for_update().select_related("group").get(code=code)
    if not is_group_admin(request.user, inv.group):
        raise PermissionDenied("沒有權限撤銷此邀請")

    if inv.is_active:
        inv.is_active = False
        inv.save(update_fields=["is_active"])
        # 你也可以 messages.success(...)，這裡走前端訊息就好
    # 導回列表
    return redirect(reverse("invite_list", args=[inv.group_id]))


@login_required
def create_invitation(request, group_id, device_id):
    group = get_object_or_404(Group, pk=group_id)
    device = get_object_or_404(Device, pk=device_id)

    if not is_group_admin(request.user, group):
        raise PermissionDenied("無權限建立邀請")

    if not group.devices.filter(pk=device.pk).exists():
        return render(request, "invites/error.html", {"message": "此裝置不在群組中"})

    if request.method == "POST":
        role = (request.POST.get("role") or "operator").lower()
        # ⭐ 強制單次使用
        max_uses = 1
        # 到期時間（預設 7 天）
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
        invite_url = request.build_absolute_uri(f"/invites/accept/{inv.code}/")
        return render(
            request, "invites/created.html", {"invite_url": invite_url, "inv": inv}
        )

    return render(request, "invites/create.html", {"group": group, "device": device})


def accept_invite(request, code):
    inv = get_object_or_404(Invitation, code=code)
    if not inv.is_valid():
        return render(request, "invites/invalid.html")

    if request.user.is_authenticated:
        _join_and_consume(inv, request.user)
        return render(
            request, "invites/success.html", {"group": inv.group, "device": inv.device}
        )

    if request.method == "POST":
        if "login" in request.POST:
            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                login(request, form.get_user())
                _join_and_consume(inv, request.user)
                return render(
                    request,
                    "invites/success.html",
                    {"group": inv.group, "device": inv.device},
                )
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
                login(request, user)
                _join_and_consume(inv, user)
                return render(
                    request,
                    "invites/success.html",
                    {"group": inv.group, "device": inv.device},
                )
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
    # 重新抓一遍並加鎖（避免兩人同時使用同一 code）
    inv = Invitation.objects.select_for_update().select_related("group").get(pk=inv.pk)

    if inv.email and inv.email.lower() != user.email.lower():
        raise PermissionDenied("此邀請僅限特定信箱使用")

    GroupMembership.objects.get_or_create(
        user=user, group=inv.group, defaults={"role": inv.role or "operator"}
    )

    # 若沒綁 email，消費時把使用者 email 記錄住（方便稽核）
    if not inv.email:
        inv.email = user.email

    # 建議 consume 內部也驗證 is_valid()
    inv.consume()
    inv.save(update_fields=["email", "used_count", "is_active"])
