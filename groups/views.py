from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from datetime import timedelta
from django.utils.translation import gettext_lazy as _
from invites.models import Invitation, InvitationDevice
from django.http import HttpResponseForbidden

from .models import (
    Group,
    GroupMembership,
    GroupDevice,
    DeviceShareRequest,
    GroupShareGrant,
    GroupDevicePermission,
)
from .permissions import can_attach_device_to_group, is_group_admin
from .permissions import (
    has_active_share_grant,
    can_detach_device_from_group,
)
from .forms import (
    GroupForm,
    AddMemberForm,
    UpdateMemberForm,
    make_invite_device_formset,
)
from pi_devices.models import Device
from .forms import GroupCreateForm, AddMemberForm, UpdateMemberForm
from pi_devices.forms import MemberDeviceACLForm
from invites.models import Invitation
from collections import defaultdict

from notifications.services import (
    notify_invite_created,  # 邀請建立
    notify_member_role_changed,  # 角色變更
    notify_member_removed,  # 成員移除
    notify_member_left,  # 成員退出
    notify_group_device_added,  # 群組掛入裝置
    notify_group_device_removed,  # 群組移除裝置
    notify_share_request_submitted,  # 成員送出分享申請
    notify_share_request_approved,  # 申請核准
    notify_share_request_rejected,  # 申請拒絕
    notify_share_grant_opened,  # 開通持續性授權
    notify_share_grant_revoked,  # 關閉持續性授權
    notify_group_renamed,  # 群組更改名稱
    notify_group_deleted,  # 刪除群組
    notify_group_created,  # 建立群組
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
@transaction.atomic
def group_create(request):
    if request.method == "POST":
        form = GroupCreateForm(request.POST, user=request.user)
        if form.is_valid():
            g = form.save(commit=False)
            g.owner = request.user
            g.save()

            selected_devices = list(form.cleaned_data.get("devices") or [])
            if selected_devices:
                objs = [
                    GroupDevice(group=g, device=d, added_by=request.user)
                    for d in selected_devices
                ]
                GroupDevice.objects.bulk_create(objs, ignore_conflicts=True)

                transaction.on_commit(
                    lambda: [
                        notify_group_device_added(actor=request.user, group=g, device=d)
                        for d in selected_devices
                    ]
                )

            transaction.on_commit(
                lambda: notify_group_created(group=g, actor=request.user)
            )
            messages.success(
                request,
                _("群組已建立")
                + (
                    f"，並加入 {len(selected_devices)} 台裝置"
                    if selected_devices
                    else ""
                ),
            )
            return redirect("group_detail", group_id=g.id)
    else:
        form = GroupCreateForm(user=request.user)

    has_devices = Device.objects.filter(user=request.user).exists()
    return render(
        request,
        "groups/group_form.html",
        {"form": form, "title": _("新增群組"), "has_devices": has_devices},
    )


# ========== 編輯群組（名稱） ==========
@login_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def group_update(request, group_id):
    group = get_object_or_404(Group, pk=group_id)
    if not is_group_admin(request.user, group):
        messages.error(request, "沒有權限編輯此群組")
        return redirect("group_detail", group_id=group.id)

    if request.method == "POST":
        form = GroupForm(request.POST, instance=group)
        if form.is_valid():
            old_name = group.name
            changed = set(form.changed_data)
            form.save()

            # 只有改名才通知
            if "name" in changed:
                new_name = form.cleaned_data["name"]
                transaction.on_commit(
                    lambda: notify_group_renamed(
                        group=group,
                        old_name=old_name,
                        new_name=new_name,
                        actor=request.user,
                    )
                )

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
        group_name = group.name
        group_pk = group.id
        recipient_ids = list(group.memberships.values_list("user_id", flat=True))
        recipient_ids = [uid for uid in recipient_ids if uid != request.user.id]

        group.delete()

        def _send_notifications():
            from django.contrib.auth import get_user_model

            User = get_user_model()
            recipients = User.objects.filter(id__in=recipient_ids)
            for u in recipients:
                notify_group_deleted(
                    user=u,
                    group_name=group_name,
                    group_id=group_pk,
                    actor=request.user,
                )

        transaction.on_commit(_send_notifications)

        messages.success(request, "群組已刪除")
        return redirect("home")

    return render(request, "groups/group_confirm_delete.html", {"group": group})


# ========== 群組詳情 ==========
@login_required
def group_detail(request, group_id):
    group = get_object_or_404(Group, pk=group_id)

    is_member = GroupMembership.objects.filter(group=group, user=request.user).exists()
    if (group.owner_id != request.user.id) and (not is_member):
        messages.error(request, "沒有權限檢視此群組")
        return redirect("home")

    # 群組內裝置（含 owner、加入者）
    group_devices = (
        GroupDevice.objects.filter(group=group)
        .select_related("device", "device__user", "added_by")
        .all()
    )
    device_ids_in_group = [gd.device_id for gd in group_devices]

    # 我可掛入的裝置
    attachable_devices = (
        Device.objects.filter(user=request.user)
        .exclude(groups=group)
        .select_related("user")
    )

    memberships = group.memberships.select_related("user").all()

    is_admin = is_group_admin(request.user, group)
    user_has_grant = has_active_share_grant(request.user, group)

    pending_requests = (
        group.device_share_requests.filter(status="pending").select_related(
            "requester", "device"
        )
        if (is_member or group.owner_id == request.user.id)
        else []
    )
    active_grants = group.share_grants.filter(is_active=True).select_related("user")
    granted_user_ids = list(active_grants.values_list("user_id", flat=True))

    # 我送出的、尚未審核的裝置申請（用 device_id）
    my_pending_device_ids = list(
        DeviceShareRequest.objects.filter(
            requester=request.user, group=group, status="pending"
        ).values_list("device_id", flat=True)
    )

    # ====== ACL：一次算好 ======
    # 取出所有成員在本群組的 ACL 記錄（can_control=True）
    acl_rows = GroupDevicePermission.objects.filter(
        group=group,
        user_id__in=[m.user_id for m in memberships],
        device_id__in=device_ids_in_group,
        can_control=True,
    ).values("user_id", "device_id")

    acl_map = defaultdict(set)
    for r in acl_rows:
        acl_map[r["user_id"]].add(r["device_id"])

    # 對每位成員計算 allowed_ids（給模板顯示/勾選）
    for m in memberships:
        if m.user_id == group.owner_id or m.role == "admin":
            # 群長/管理員 → 全可控
            m.allowed_ids = device_ids_in_group[:]
        elif m.role == "viewer":
            # 觀察者 → 全不可控
            m.allowed_ids = []
        else:
            # operator：
            if acl_map.get(m.user_id):
                # 有 ACL → 依 ACL
                m.allowed_ids = list(acl_map[m.user_id])
            else:
                # 沒任何 ACL → 預設全可控（符合你「預設通通都選」的需求）
                m.allowed_ids = device_ids_in_group[:]

    return render(
        request,
        "groups/group_detail.html",
        {
            "group": group,
            "devices": [gd.device for gd in group_devices],  # 若模板有用到
            "memberships": memberships,
            "attachable_devices": attachable_devices,
            "pending_requests": pending_requests,
            "active_grants": active_grants,
            "is_admin": is_admin,
            "user_has_grant": user_has_grant,
            "granted_user_ids": granted_user_ids,
            "group_devices": group_devices,
            "my_pending_device_ids": my_pending_device_ids,
            "user": request.user,
            "role_choices": GroupMembership.ROLE_CHOICES,
        },
    )


# ========== 裝置掛入 ==========
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def attach_device(request, group_id, device_id):
    group = get_object_or_404(Group, pk=group_id)
    device = get_object_or_404(Device, pk=device_id)

    if not can_attach_device_to_group(request.user, device, group):
        messages.error(request, "沒有權限將此裝置加入群組")
        return redirect("group_detail", group_id=group.id)

    gd, created = GroupDevice.objects.get_or_create(
        group=group, device=device, defaults={"added_by": request.user}
    )

    if created:
        transaction.on_commit(
            lambda: notify_group_device_added(
                actor=request.user, group=group, device=device
            )
        )
        messages.success(request, "已將裝置加入群組")
    else:
        messages.info(request, "裝置已在此群組中")

    return redirect("group_detail", group_id=group.id)


# ========== 裝置移除 ==========
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def detach_device(request, group_id, device_id):
    group = get_object_or_404(Group, pk=group_id)
    device = get_object_or_404(Device, pk=device_id)

    if not can_detach_device_from_group(request.user, device, group):
        messages.error(request, "沒有權限移除此裝置")
        return redirect("group_detail", group_id=group.id)

    deleted, _ = GroupDevice.objects.filter(group=group, device=device).delete()

    if deleted:
        transaction.on_commit(
            lambda: notify_group_device_removed(
                actor=request.user, group=group, device=device
            )
        )
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
    devices_qs = group.devices.order_by("display_name", "serial_number", "id")

    if request.method == "POST":
        form = AddMemberForm(request.POST)
        dev_fs = make_invite_device_formset(devices_qs, data=request.POST)

        if form.is_valid() and dev_fs.is_valid():
            email = form.cleaned_data["email"].lower().strip()
            role = form.cleaned_data["role"]

            if group.owner.email.lower() == email:
                messages.info(request, "此 Email 為群組擁有者，無需邀請。")
                return redirect("group_members", group_id=group.id)

            # 收集勾選的設備與權限
            selected = []
            for f in dev_fs:
                if f.cleaned_data.get("include"):
                    did = f.cleaned_data["device_id"]
                    perm = f.cleaned_data["perm"]  # "control" or "view"
                    selected.append((did, perm))

            if not selected:
                messages.error(request, "請至少勾選一台裝置或設定權限。")
                return render(
                    request,
                    "groups/group_members.html",
                    {
                        "group": group,
                        "memberships": memberships,
                        "form": form,
                        "dev_formset": dev_fs,
                        "role_choices": GroupMembership.ROLE_CHOICES,
                        "dev_pairs": list(zip(devices_qs, dev_fs.forms)),
                    },
                )

            # === 一張邀請卡（不綁單一 device；多台用 InvitationDevice 表）===
            inv = None
            for _ in range(5):
                try:
                    inv = Invitation.objects.create(
                        group=group,
                        device=None,  # ★ 關鍵：一張卡對應多設備，這裡不要塞單一裝置
                        invited_by=request.user,
                        email=email or None,
                        role=role,
                        max_uses=1,
                        expires_at=timezone.now() + timedelta(days=7),
                    )
                    break
                except IntegrityError as e:
                    # 邀請碼 code 撞到就重試，其他錯拋出
                    if "invites_invitation.code" in str(e):
                        continue
                    raise

            if not inv:
                messages.error(request, "產生邀請碼失敗，請再試一次")
                return redirect("group_members", group_id=group.id)

            # 寫入每台設備的 ACL（InvitationDevice）
            items = []
            for did, perm in selected:
                device = get_object_or_404(Device, pk=did)
                if not group.devices.filter(pk=device.pk).exists():
                    # 避免被竄改 device_id（不在群組內就跳過）
                    continue
                item = InvitationDevice.objects.create(
                    invitation=inv,
                    device=device,
                    can_control=(perm == "control"),
                )
                items.append(item)

            # 提交後再發通知
            transaction.on_commit(lambda: notify_invite_created(invitation=inv))

            invite_url = request.build_absolute_uri(f"/invites/accept/{inv.code}/")
            return render(
                request,
                "invites/created.html",
                {
                    "invite_url": invite_url,
                    "inv": inv,
                    "group": group,
                    "items": items,  # 或 inv.device_items.select_related("device").all()
                },
            )

        # 表單驗證失敗 → 回填
        return render(
            request,
            "groups/group_members.html",
            {
                "group": group,
                "memberships": memberships,
                "form": form,
                "dev_formset": dev_fs,
                "role_choices": GroupMembership.ROLE_CHOICES,
                "dev_pairs": list(zip(devices_qs, dev_fs.forms)),
            },
        )

    # GET
    form = AddMemberForm()
    dev_fs = make_invite_device_formset(devices_qs)
    return render(
        request,
        "groups/group_members.html",
        {
            "group": group,
            "memberships": memberships,
            "form": form,
            "dev_formset": dev_fs,
            "role_choices": GroupMembership.ROLE_CHOICES,
            "dev_pairs": list(zip(devices_qs, dev_fs.forms)),
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
        new_role = form.cleaned_data["role"]
        old_role = ms.role

        if new_role == old_role:
            messages.info(request, "角色未變更")
            return redirect("group_members", group_id=group.id)

        ms.role = new_role
        ms.save(update_fields=["role"])

        transaction.on_commit(
            lambda: notify_member_role_changed(
                actor=request.user,
                group=group,
                member=ms.user,
                old_role=old_role,
                new_role=new_role,
            )
        )

        messages.success(request, "角色已更新")
    else:
        messages.error(request, "更新失敗，請確認欄位")

    return redirect("group_detail", group_id=group.id)


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
    target_user = ms.user

    if target_user.id == group.owner_id:
        messages.error(request, "不可移除群組擁有者")
        return redirect("group_members", group_id=group.id)

    ms.delete()

    transaction.on_commit(
        lambda: notify_member_removed(
            actor=request.user, group=group, member=target_user
        )
    )

    messages.success(request, "成員已移除")
    return redirect("group_members", group_id=group.id)


# ========== 成員：提出分享裝置申請 ==========
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def request_share_device(request, group_id, device_id):
    """
    一般成員送出分享申請
    """
    group = get_object_or_404(Group, pk=group_id)
    device = get_object_or_404(Device, pk=device_id)

    if getattr(device, "user_id", None) != request.user.id:
        messages.error(request, "僅裝置擁有者可提出申請")
        return redirect("group_detail", group_id=group.id)

    if (
        not GroupMembership.objects.filter(group=group, user=request.user).exists()
        and group.owner_id != request.user.id
    ):
        messages.error(request, "你不是此群組成員，無法提出申請")
        return redirect("group_detail", group_id=group.id)

    if GroupDevice.objects.filter(group=group, device=device).exists():
        messages.info(request, "此裝置已在群組中，無需提出申請")
        return redirect("group_detail", group_id=group.id)

    msg = (request.POST.get("message") or "").strip()

    try:
        dsr = DeviceShareRequest.objects.create(
            requester=request.user,
            group=group,
            device=device,
            message=msg,
        )

        transaction.on_commit(
            lambda: notify_share_request_submitted(
                requester=request.user, group=group, device=device
            )
        )

        messages.success(request, "已送出分享申請，待管理員審核")
    except IntegrityError:
        messages.info(request, "已有待審核的相同申請，請等待管理員處理")

    return redirect("group_detail", group_id=group.id)


# ========== 管理員核准／拒絕 ==========
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def review_share_request(request, group_id, req_id):
    group = get_object_or_404(Group, pk=group_id)
    if not is_group_admin(request.user, group):
        messages.error(request, "沒有權限審核")
        return redirect("group_detail", group_id=group.id)

    dsr = get_object_or_404(
        DeviceShareRequest, pk=req_id, group=group, status="pending"
    )
    action = (request.POST.get("action") or "").lower()

    if action == "approve":
        dsr.status = "approved"
        dsr.reviewed_by = request.user
        dsr.reviewed_at = timezone.now()
        dsr.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        gd, created = GroupDevice.objects.get_or_create(
            group=group, device=dsr.device, defaults={"added_by": dsr.requester}
        )

        transaction.on_commit(lambda: notify_share_request_approved(request=dsr))

        if created:
            transaction.on_commit(
                lambda: notify_group_device_added(
                    actor=request.user, group=group, device=dsr.device
                )
            )
            messages.success(request, "已核准並加入裝置")
        else:
            messages.info(request, "已核准；此裝置原本就在群組中")

    elif action == "reject":
        dsr.status = "rejected"
        dsr.reviewed_by = request.user
        dsr.reviewed_at = timezone.now()
        dsr.save(update_fields=["status", "reviewed_by", "reviewed_at"])

        transaction.on_commit(lambda: notify_share_request_rejected(request=dsr))
        messages.info(request, "已拒絕該申請")

    else:
        messages.error(request, "無效的操作")
        return redirect("group_detail", group_id=group.id)

    return redirect("group_detail", group_id=group.id)


# ========== 管理員開/關持續性授權 ==========
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def grant_share_permission(request, group_id, user_id):
    group = get_object_or_404(Group, pk=group_id)
    if not is_group_admin(request.user, group):
        messages.error(request, "沒有權限開通授權")
        return redirect("group_detail", group_id=group.id)

    target_member = get_object_or_404(GroupMembership, group=group, user_id=user_id)
    user = target_member.user

    expires_at = None
    raw_days = (request.POST.get("expires_days") or "").strip()
    if raw_days:
        try:
            days = int(raw_days)
            if days > 0:
                expires_at = timezone.now() + timedelta(days=days)
        except ValueError:
            pass

    created = False
    grant = GroupShareGrant.objects.filter(
        user=user, group=group, is_active=True
    ).first()

    if grant:
        if expires_at:
            grant.expires_at = expires_at
            grant.save(update_fields=["expires_at"])
    else:
        grant = (
            GroupShareGrant.objects.filter(user=user, group=group, is_active=False)
            .order_by("-created_at")
            .first()
        )
        if grant:
            grant.is_active = True
            grant.created_by = request.user
            grant.expires_at = expires_at
            grant.save(update_fields=["is_active", "created_by", "expires_at"])
            created = True
        else:
            grant = GroupShareGrant.objects.create(
                user=user,
                group=group,
                created_by=request.user,
                expires_at=expires_at,
                is_active=True,
            )
            created = True

    transaction.on_commit(
        lambda: notify_share_grant_opened(
            actor=request.user, group=group, user=user, grant=grant, created=created
        )
    )

    messages.success(request, "已開通（或更新）持續性分享授權")
    return redirect("group_detail", group_id=group_id)


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def revoke_share_permission(request, group_id, user_id):
    group = get_object_or_404(Group, pk=group_id)
    if not is_group_admin(request.user, group):
        messages.error(request, "沒有權限關閉授權")
        return redirect("group_detail", group_id=group.id)

    updated = GroupShareGrant.objects.filter(
        user_id=user_id, group=group, is_active=True
    ).update(is_active=False)

    if updated > 0:
        transaction.on_commit(
            lambda: notify_share_grant_revoked(
                actor=request.user, group=group, user_id=user_id
            )
        )
        messages.info(request, "已關閉該成員的分享授權")
    else:
        messages.info(request, "未找到需關閉的有效授權")

    return redirect("group_detail", group_id=group_id)


@login_required
@require_http_methods(["GET", "POST"])
def member_acl_edit(request, group_id, user_id):
    group = get_object_or_404(Group, pk=group_id)
    if not is_group_admin(request.user, group):
        messages.error(request, "沒有權限")
        return redirect("group_members", group_id=group.id)

    member = get_object_or_404(GroupMembership, group=group, user_id=user_id)
    current_qs = GroupDevicePermission.objects.filter(group=group, user_id=user_id)

    if request.method == "POST":
        form = MemberDeviceACLForm(request.POST, group=group)
        if form.is_valid():
            wanted = set(form.cleaned_data["devices"].values_list("id", flat=True))
            has = set(current_qs.values_list("device_id", flat=True))
            add_ids = wanted - has
            del_ids = has - wanted
            if add_ids:
                GroupDevicePermission.objects.bulk_create(
                    [
                        GroupDevicePermission(
                            user_id=user_id,
                            group=group,
                            device_id=did,
                            can_control=True,
                        )
                        for did in add_ids
                    ]
                )
            if del_ids:
                GroupDevicePermission.objects.filter(
                    group=group, user_id=user_id, device_id__in=del_ids
                ).delete()
            messages.success(request, "已更新裝置權限")
            return redirect("group_members", group_id=group.id)
    else:
        preset = current_qs.values_list("device_id", flat=True)
        form = MemberDeviceACLForm(group=group, initial={"devices": list(preset)})

    return render(
        request,
        "groups/member_acl_edit.html",
        {"group": group, "member": member, "form": form},
    )


@login_required
@require_http_methods(["GET"])
def member_device_acl(request, group_id, user_id):
    group = get_object_or_404(Group, pk=group_id)
    if not is_group_admin(request.user, group):
        return HttpResponseForbidden("沒有權限")

    member = get_object_or_404(GroupMembership, group=group, user_id=user_id)

    # 群組所有裝置
    devices = group.devices.select_related("user").order_by(
        "display_name", "serial_number", "id"
    )

    # 讀出該 member 現有 ACL
    perms = {
        p.device_id: p.can_control
        for p in GroupDevicePermission.objects.filter(
            group=group, user_id=user_id, device__in=devices
        )
    }

    # 預設允許：若沒有 perm => True
    rows = []
    for d in devices:
        allowed = perms.get(d.id, True)
        rows.append({"device": d, "allowed": allowed})

    return render(
        request,
        "groups/member_device_acl.html",
        {"group": group, "member": member, "rows": rows},
    )


@login_required
@require_http_methods(["POST"])
@transaction.atomic
def member_device_acl(request, group_id, user_id):
    """
    調整某位成員在本群組內，對各裝置的可操作權限（只對 operator 有效）。
    表單欄位：dev[] = 多個 device_id（勾選者視為 can_control=True）
    """
    group = get_object_or_404(Group, pk=group_id)
    if not is_group_admin(request.user, group):
        return HttpResponseForbidden("沒有權限")

    ms = get_object_or_404(GroupMembership, group=group, user_id=user_id)

    # 保護：群長/管理員不需要 ACL；viewer 一律不可控
    if ms.user_id == group.owner_id:
        messages.error(request, "群長的權限不可更改。")
        return redirect("group_detail", group_id=group.id)

    if ms.role == "admin":
        # Admin 對所有裝置皆可控，清掉多餘 ACL
        GroupDevicePermission.objects.filter(group=group, user_id=user_id).delete()
        messages.info(request, "Admin 對所有裝置皆可控，無需設定。")
        return redirect("group_detail", group_id=group.id)

    if ms.role == "viewer":
        # Viewer 全不可控，清掉 ACL
        GroupDevicePermission.objects.filter(group=group, user_id=user_id).delete()
        messages.success(request, "已套用 viewer（全部不可控）。")
        return redirect("group_detail", group_id=group.id)

    # operator：把勾選的 device 視為可控
    posted_ids = set()
    for v in request.POST.getlist("dev[]"):
        try:
            posted_ids.add(int(v))
        except ValueError:
            pass

    # 僅允許本群組內的裝置
    valid_ids = set(
        GroupDevice.objects.filter(group=group, device_id__in=posted_ids).values_list(
            "device_id", flat=True
        )
    )

    # 先清掉舊的 ACL，再重建
    GroupDevicePermission.objects.filter(group=group, user_id=user_id).delete()
    objs = [
        GroupDevicePermission(
            group=group, user_id=user_id, device_id=did, can_control=True
        )
        for did in valid_ids
    ]
    if objs:
        GroupDevicePermission.objects.bulk_create(objs)

    messages.success(request, "已更新裝置權限。")
    return redirect("group_detail", group_id=group.id)


@login_required
@require_POST
def group_leave(request, group_id):
    group = get_object_or_404(Group, pk=group_id)

    # 群長不可退出
    if request.user.id == group.owner_id:
        messages.error(request, "群長不能退出群組。")
        return redirect("group_detail", group_id=group.id)

    # 必須原本就是成員
    membership = GroupMembership.objects.filter(group=group, user=request.user).first()
    if not membership:
        messages.info(request, "你不是此群組成員。")
        return redirect("home")

    with transaction.atomic():
        # 清掉在此群組的裝置操控 ACL（若你有此模型）
        GroupDevicePermission.objects.filter(group=group, user=request.user).delete()
        membership.delete()

        # 發送退出群組通知
        transaction.on_commit(
            lambda: notify_member_left(
                actor=request.user, group=group, member=request.user
            )
        )

    messages.success(request, f"已退出「{group.name}」。")
    # 退出後轉跳首頁
    return redirect("home")
