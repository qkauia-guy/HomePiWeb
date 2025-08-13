from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from .models import Group, GroupMembership, GroupDevice
from .permissions import can_attach_device_to_group, is_group_admin
from .forms import GroupForm, AddMemberForm, UpdateMemberForm
from pi_devices.models import Device
from invites.models import Invitation
from django.utils import timezone
from datetime import timedelta


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

    # 只有擁有者或成員可看（如果你已用這段就保留）
    is_member = GroupMembership.objects.filter(group=group, user=request.user).exists()
    if (group.owner_id != request.user.id) and (not is_member):
        messages.error(request, "沒有權限檢視此群組")
        return redirect("group_list")

    devices = group.devices.select_related("user").all()

    # ⭐ 新增這行：把「自己擁有但不在群組」的裝置撈出來
    attachable_devices = (
        Device.objects.filter(user=request.user)
        .exclude(groups=group)
        .select_related("user")
    )

    memberships = group.memberships.select_related("user").all()
    return render(
        request,
        "groups/group_detail.html",
        {
            "group": group,
            "devices": devices,
            "memberships": memberships,
            "attachable_devices": attachable_devices,  # ← 傳給模板
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
