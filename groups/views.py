from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from .models import (
    Group,
    GroupMembership,
    GroupDevice,
    DeviceShareRequest,
    GroupShareGrant,
)
from .permissions import can_attach_device_to_group, is_group_admin
from .forms import GroupForm, AddMemberForm, UpdateMemberForm
from pi_devices.models import Device
from invites.models import Invitation
from django.utils import timezone
from datetime import timedelta
from .permissions import (
    is_group_admin,
    has_active_share_grant,
    can_detach_device_from_group,
)


# ========== 群組列表 ==========
@login_required
def group_list(request):
    groups = (
        Group.objects.filter(Q(owner=request.user) | Q(memberships__user=request.user))
        .distinct()
        .select_related("owner")
    )
    return render(request, "groups/group_list.html", {"groups": groups})


# ========== 新增群組 ==========
@login_required
@require_http_methods(["GET", "POST"])
def group_create(request):
    if request.method == "POST":
        form = GroupForm(request.POST)
        if form.is_valid():
            g = form.save(commit=False)
            g.owner = request.user
            g.save()
            messages.success(request, "群組已建立")
            return redirect("group_detail", group_id=g.id)
    else:
        form = GroupForm()
    return render(
        request, "groups/group_form.html", {"form": form, "title": "新增群組"}
    )


# ========== 編輯群組（名稱） ==========
@login_required
@require_http_methods(["GET", "POST"])
def group_update(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    if not is_group_admin(request.user, group):
        messages.error(request, "沒有權限編輯此群組")
        return redirect("group_detail", group_id=group.id)

    if request.method == "POST":
        form = GroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            messages.success(request, "群組已更新")
            return redirect("group_detail", group_id=group.id)
    else:
        form = GroupForm(instance=group)
    return render(
        request, "groups/group_form.html", {"form": form, "title": "編輯群組"}
    )


# ========== 刪除群組 ==========
@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def group_delete(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    if group.owner_id != request.user.id:
        messages.error(request, "只有群組擁有者可以刪除群組")
        return redirect("group_detail", group_id=group.id)

    if request.method == "POST":
        group.delete()
        messages.success(request, "群組已刪除")
        return redirect("group_list")
    return render(request, "groups/group_confirm_delete.html", {"group": group})


# ========== 群組詳情（需成員或擁有者） ==========
@login_required
def group_detail(request, group_id):
    group = get_object_or_404(Group, pk=group_id)

    is_member = GroupMembership.objects.filter(group=group, user=request.user).exists()
    if (group.owner_id != request.user.id) and (not is_member):
        messages.error(request, "沒有權限檢視此群組")
        return redirect("group_list")

    devices = group.devices.select_related("user").all()
    attachable_devices = (
        Device.objects.filter(user=request.user)
        .exclude(groups=group)
        .select_related("user")
    )
    memberships = group.memberships.select_related("user").all()

    is_admin = is_group_admin(request.user, group)
    user_has_grant = has_active_share_grant(request.user, group)  # ← ★ 有效授權？

    pending_requests = (
        group.device_share_requests.filter(status="pending").select_related(
            "requester", "device"
        )
        if (is_member or group.owner_id == request.user.id)
        else []
    )
    active_grants = group.share_grants.filter(is_active=True).select_related("user")
    granted_user_ids = list(active_grants.values_list("user_id", flat=True))

    group_devices = (
        GroupDevice.objects.filter(group=group)
        .select_related("device", "device__user", "added_by")
        .all()
    )
    return render(
        request,
        "groups/group_detail.html",
        {
            "group": group,
            "devices": devices,
            "memberships": memberships,
            "attachable_devices": attachable_devices,
            "pending_requests": pending_requests,
            "active_grants": active_grants,
            "is_admin": is_admin,
            "user_has_grant": user_has_grant,
            "granted_user_ids": granted_user_ids,
            "group_devices": group_devices,
        },
    )


# ========== 裝置掛入/移除（POST） ==========
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def attach_device(request, group_id, device_id):
    group = get_object_or_404(Group, pk=group_id)
    device = get_object_or_404(Device, pk=device_id)

    if not can_attach_device_to_group(request.user, device, group):
        messages.error(request, "沒有權限將此裝置加入群組")
        return redirect("group_detail", group_id=group.id)

    GroupDevice.objects.get_or_create(
        group=group, device=device, defaults={"added_by": request.user}
    )
    messages.success(request, "已將裝置加入群組")
    return redirect("group_detail", group_id=group.id)


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def detach_device(request, group_id, device_id):
    group = get_object_or_404(Group, pk=group_id)
    device = get_object_or_404(Device, pk=device_id)

    if not is_group_admin(request.user, group):
        messages.error(request, "沒有權限移除此裝置")
        return redirect("group_detail", group_id=group.id)

    GroupDevice.objects.filter(group=group, device=device).delete()
    messages.success(request, "已從群組移除裝置")
    return redirect("group_detail", group_id=group.id)


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def detach_device(request, group_id, device_id):
    group = get_object_or_404(Group, pk=group_id)
    device = get_object_or_404(Device, pk=device_id)

    if not can_detach_device_from_group(request.user, device, group):
        messages.error(request, "沒有權限移除此裝置")
        return redirect("group_detail", group_id=group.id)

    # 僅刪除此群組的關聯
    deleted, _ = GroupDevice.objects.filter(group=group, device=device).delete()
    if deleted:
        messages.success(request, "已從群組移除裝置")
    else:
        messages.info(request, "裝置不在此群組內")
    return redirect("group_detail", group_id=group.id)


# ========== 成員管理：列表 + 新增 ==========
@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def group_members(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    if not is_group_admin(request.user, group):
        messages.error(request, "沒有權限管理此群組成員")
        return redirect("group_detail", group_id=group.id)

    memberships = group.memberships.select_related("user").all()

    # 沒有裝置就無法建立邀請（需要綁一台裝置）
    if not group.devices.exists():
        messages.info(request, "此群組尚無裝置，請先將裝置加入群組後再建立邀請。")

    if request.method == "POST":
        form = AddMemberForm(request.POST)
        # 注入當前群組的裝置選單
        form.fields["device"].queryset = group.devices.all()
        if form.is_valid():
            email = form.cleaned_data["email"].lower()
            role = form.cleaned_data["role"]
            device = form.cleaned_data["device"]

            # 不要對擁有者發邀請
            if group.owner.email.lower() == email:
                messages.info(request, "此 Email 為群組擁有者，無需邀請。")
                return redirect("group_members", group_id=group.id)

            # 建立「單次、可選綁 email」的邀請（預設 7 天）
            inv = Invitation.objects.create(
                group=group,
                device=device,
                invited_by=request.user,
                email=email,  # 綁定該信箱；受邀者必須用這個 email 接受
                role=role,  # viewer / operator
                max_uses=1,  # 單次使用
                expires_at=timezone.now() + timedelta(days=7),
            )

            # 生成可分享連結
            invite_url = request.build_absolute_uri(f"/invites/accept/{inv.code}/")
            # 直接顯示「已建立頁」給擁有者/管理員複製
            return render(
                request, "invites/created.html", {"invite_url": invite_url, "inv": inv}
            )
    else:
        form = AddMemberForm()
        form.fields["device"].queryset = group.devices.all()

    return render(
        request,
        "groups/group_members.html",
        {
            "group": group,
            "memberships": memberships,
            "form": form,
            "role_choices": GroupMembership.ROLE_CHOICES,  # 供下方列表的角色下拉使用
        },
    )


# ========== 成員：修改角色 ==========
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def member_set_role(request, group_id, membership_id):
    group = get_object_or_404(Group, pk=group_id)
    if not is_group_admin(request.user, group):
        messages.error(request, "沒有權限")
        return redirect("group_members", group_id=group.id)

    ms = get_object_or_404(GroupMembership, pk=membership_id, group=group)
    form = UpdateMemberForm(request.POST)
    if form.is_valid():
        ms.role = form.cleaned_data["role"]
        ms.save(update_fields=["role"])
        messages.success(request, "角色已更新")
    else:
        messages.error(request, "更新失敗，請確認欄位")
    return redirect("group_members", group_id=group.id)


# ========== 成員：移除 ==========
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def member_remove(request, group_id, membership_id):
    group = get_object_or_404(Group, pk=group_id)
    if not is_group_admin(request.user, group):
        messages.error(request, "沒有權限")
        return redirect("group_members", group_id=group.id)

    ms = get_object_or_404(GroupMembership, pk=membership_id, group=group)
    ms.delete()
    messages.success(request, "成員已移除")
    return redirect("group_members", group_id=group.id)


# ========== 成員：權限不足，提出分享裝置申請 ==========
# 條件：必須是裝置擁有者 & 群組成員；重複 pending 會被 UniqueConstraint 擋下
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def request_share_device(request, group_id, device_id):
    """
    一般成員送出「某台裝置→某群組」分享申請
    條件：必須是裝置擁有者 & 群組成員；重複 pending 會被 UniqueConstraint 擋下
    """
    group = get_object_or_404(Group, pk=group_id)
    device = get_object_or_404(Device, pk=device_id)

    # 基本檢查
    if getattr(device, "user_id", None) != request.user.id:
        messages.error(request, "僅裝置擁有者可提出申請")
        return redirect("group_detail", group_id=group.id)

    if (
        not GroupMembership.objects.filter(group=group, user=request.user).exists()
        and group.owner_id != request.user.id
    ):
        messages.error(request, "你不是此群組成員，無法提出申請")
        return redirect("group_detail", group_id=group.id)

    msg = (request.POST.get("message") or "").strip()
    try:
        DeviceShareRequest.objects.create(
            requester=request.user,
            group=group,
            device=device,
            message=msg,
        )
        messages.success(request, "已送出分享申請，待管理員審核")
    except Exception:
        messages.info(request, "已有待審核的相同申請，請等待管理員處理")
    return redirect("group_detail", group_id=group.id)


# ========== 管理員核准／拒絕 ==========
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def review_share_request(request, group_id, req_id):
    """
    管理員審核申請：approved → 直接建立 GroupDevice（一次性完成分享）
                      rejected → 標記拒絕
    """
    group = get_object_or_404(Group, pk=group_id)
    if not is_group_admin(request.user, group):
        messages.error(request, "沒有權限審核")
        return redirect("group_detail", group_id=group.id)

    dsr = get_object_or_404(
        DeviceShareRequest, pk=req_id, group=group, status="pending"
    )
    action = request.POST.get("action")  # 'approve' or 'reject'

    if action == "approve":
        dsr.status = "approved"
        dsr.reviewed_by = request.user
        dsr.reviewed_at = timezone.now()
        dsr.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        # 一次性：直接把這台裝置加入群組（由申請人作為 added_by）
        GroupDevice.objects.get_or_create(
            group=group, device=dsr.device, defaults={"added_by": dsr.requester}
        )
        messages.success(request, "已核准並加入裝置")
    else:
        dsr.status = "rejected"
        dsr.reviewed_by = request.user
        dsr.reviewed_at = timezone.now()
        dsr.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        messages.info(request, "已拒絕該申請")

    return redirect("group_detail", group_id=group.id)


# ========== 管理員開/關「持續性授權」 ==========
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def grant_share_permission(request, group_id, user_id):
    """
    管理員對某位成員開通「持續性分享授權」
    開通後：該成員只要是裝置擁有者、且為群組成員，即可自己 attach 裝置（不再需逐次申請）
    """
    group = get_object_or_404(Group, pk=group_id)
    if not is_group_admin(request.user, group):
        messages.error(request, "沒有權限開通授權")
        return redirect("group_detail", group_id=group.id)

    target_member = get_object_or_404(GroupMembership, group=group, user_id=user_id)

    expires_days = request.POST.get("expires_days")
    expires_at = None
    if expires_days:
        try:
            days = int(expires_days)
            expires_at = timezone.now() + timedelta(days=days)
        except ValueError:
            pass

    grant, created = GroupShareGrant.objects.get_or_create(
        user=target_member.user,
        group=group,
        defaults={
            "created_by": request.user,
            "expires_at": expires_at,
            "is_active": True,
        },
    )
    if not created:
        # 已存在 active grant，就更新到期日（若有輸入）
        if expires_at:
            grant.expires_at = expires_at
            grant.save(update_fields=["expires_at"])

    messages.success(request, "已開通（或更新）持續性分享授權")
    return redirect("group_detail", group_id=group.id)


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def revoke_share_permission(request, group_id, user_id):
    """
    管理員關閉某位成員的持續性授權
    """
    group = get_object_or_404(Group, pk=group_id)
    if not is_group_admin(request.user, group):
        messages.error(request, "沒有權限關閉授權")
        return redirect("group_detail", group_id=group.id)

    GroupShareGrant.objects.filter(user_id=user_id, group=group, is_active=True).update(
        is_active=False
    )
    messages.info(request, "已關閉該成員的分享授權")
    return redirect("group_detail", group_id=group.id)
