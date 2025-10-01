from urllib.parse import urlparse, parse_qs

from django.contrib import messages
from django.contrib.messages import get_messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render, redirect
from django.db.models import Q
from django.urls import reverse

from ..models import Device, DeviceCapability
from ..forms import DeviceCapabilityForm
from groups.models import Group, GroupDevice, GroupMembership

# 佇列工具：沿用 api.py 的一致行為（TTL、欄位）
from .api import _queue_command
from django.middleware.csrf import get_token


# 你原本的常數，保留以供其他能力映射使用
ALLOWED = {
    "light": {"light_on", "light_off", "light_toggle"},
    "fan": {"fan_on", "fan_off", "fan_set_speed"},
    "locker": {"locker_lock", "locker_unlock", "locker_toggle"},
}


# ========== CRUD ==========


@login_required
def create(request, device_id):
    device = get_object_or_404(Device, pk=device_id, user=request.user)
    if request.method == "POST":
        form = DeviceCapabilityForm(request.POST)
        if form.is_valid():
            cap = form.save(commit=False)
            cap.device = device
            cap.save()
            messages.success(request, "能力已新增")
            return redirect(device.get_absolute_url())
    else:
        form = DeviceCapabilityForm()
    return render(
        request, "pi_devices/capability_form.html", {"form": form, "device": device}
    )


@login_required
def edit(request, device_id, cap_id):
    device = get_object_or_404(Device, pk=device_id, user=request.user)
    cap = get_object_or_404(DeviceCapability, pk=cap_id, device=device)
    if request.method == "POST":
        form = DeviceCapabilityForm(request.POST, instance=cap)
        if form.is_valid():
            form.save()
            messages.success(request, "能力已更新")
            return redirect(device.get_absolute_url())
    else:
        form = DeviceCapabilityForm(instance=cap)
    return render(
        request,
        "pi_devices/capability_form.html",
        {"form": form, "device": device, "cap": cap},
    )


@login_required
def delete(request, device_id, cap_id):
    device = get_object_or_404(Device, pk=device_id, user=request.user)
    cap = get_object_or_404(DeviceCapability, pk=cap_id, device=device)
    if request.method == "POST":
        cap.delete()
        messages.success(request, "能力已刪除")
        return redirect(device.get_absolute_url())
    return render(
        request,
        "pi_devices/capability_confirm_delete.html",
        {"device": device, "cap": cap},
    )


# ========== helpers ==========


def _parse_gid(val):
    if not val:
        return None
    try:
        if isinstance(val, str) and val.startswith("g"):
            return int(val[1:])
        return int(val)
    except (TypeError, ValueError):
        return None


def _current_group_from_request(request):
    """若你需要從 next=?g=gXX 取群組，可用這個。"""
    gid = (
        request.POST.get("group_id")
        or request.GET.get("group_id")
        or request.POST.get("g")
        or request.GET.get("g")
    )
    gid = _parse_gid(gid)
    if gid:
        return gid
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    try:
        gparam = parse_qs(urlparse(nxt).query).get("g", [None])[0]
        return _parse_gid(gparam)
    except Exception:
        return None


def _can_control(user, group: Group) -> bool:
    """依你現有權限模型調整；目前為：擁有者或成員即可控制。"""
    if group.owner_id == user.id:
        return True
    return group.memberships.filter(user=user).exists()


def _resolve_group(request, device: Device):
    """
    從表單/URL 解析 group，並做包含性與權限檢查。
    回傳：(group | None, error_message | None, raw_gid_str)
    """
    gid_raw = (
        request.POST.get("group_id")
        or request.GET.get("group_id")
        or request.POST.get("g")
        or request.GET.get("g")
        or ""
    )
    gid = None
    if gid_raw:
        try:
            gid = int(gid_raw[1:]) if str(gid_raw).startswith("g") else int(gid_raw)
        except Exception:
            gid = None

    if gid:
        group = get_object_or_404(Group, pk=gid)
        if not GroupDevice.objects.filter(group=group, device=device).exists():
            return None, "Device not in group", gid_raw
        if not _can_control(request.user, group):
            return None, "No permission", gid_raw
        return group, None, gid_raw

    group = (
        Group.objects.filter(devices=device)
        .filter(Q(owner=request.user) | Q(memberships__user=request.user))
        .distinct()
        .first()
    )
    if not group or not _can_control(request.user, group):
        return None, "No permission", gid_raw
    return group, None, f"g{group.id}"


# ========== Actions ==========


@login_required
@require_POST
def action(request, device_id: int, cap_id: int, action: str):
    """
    傳統 action 入口：/devices/<device_id>/cap/<cap_id>/action/<action>/
    - light: on/off/toggle
    - camera: start/stop/status
    這裡改為使用 _queue_command()；其餘導回行為維持不變。
    """
    device = get_object_or_404(Device, pk=device_id)
    cap = get_object_or_404(DeviceCapability, pk=cap_id, device=device)

    # 權限與群組解析
    group, err, gid_raw = _resolve_group(request, device)
    if err:
        return HttpResponseForbidden(err)

    kind = (cap.kind or "").lower()
    if kind == "light":
        mapping = {"on": "light_on", "off": "light_off", "toggle": "light_toggle"}
    elif kind in ("camera", "cam"):
        mapping = {
            "start": "camera_start",
            "stop": "camera_stop",
            "status": "camera_status",
        }
    elif kind == "locker":
        mapping = {
            "lock": "locker_lock",
            "unlock": "locker_unlock",
            "toggle": "locker_toggle",
        }
    else:
        mapping = {}

    cmd_name = mapping.get((action or "").lower())
    if cmd_name:
        payload = {}
        if getattr(cap, "slug", None):
            payload["target"] = cap.slug  # ★ agent 用
            payload["slug"] = cap.slug
        _queue_command(device, cmd_name, payload=payload)
        
        # 發送通知給群組成員
        try:
            from notifications.services.devices import notify_device_action
            
            # 除錯資訊
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Device action notification (action view): device={device.id}, action={cmd_name}, actor={request.user.id}, group={group}")
            
            # 發送通知
            result = notify_device_action(
                device=device,
                action=cmd_name,
                actor=request.user,
                group=group,
                capability_name=cap.name,
            )
            
            logger.info(f"Notification result (action view): {len(result) if result else 0} notifications created")
            
        except Exception as e:
            # 通知失敗不影響主要功能，只記錄錯誤
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to send device action notification: {e}")
            import traceback
            logger.warning(f"Traceback: {traceback.format_exc()}")

    next_url = request.POST.get("next")
    if not next_url:
        next_url = reverse("home") + f"?g={gid_raw}&d={device.id}&cap={cap.id}"
    return redirect(next_url)


@login_required
@require_POST
def capability_action(request, device_id: int, cap_id: int, action: str):
    """
    /devices/<device_id>/caps/<cap_id>/<action>/

    既有：
    - light: on/off/toggle -> 佇列 light_on / light_off / light_toggle
    - camera: start/stop/status -> 佇列 camera_start / camera_stop / camera_status

    新增：
    - auto_on / auto_off -> 佇列 auto_light_on / auto_light_off
      （payload 可選帶門檻與去抖動參數）
    """
    device = get_object_or_404(Device, pk=device_id)
    cap = get_object_or_404(DeviceCapability, pk=cap_id, device=device)

    # ===== 權限檢查 =====
    gid_raw = request.POST.get("group_id") or request.GET.get("group_id") or ""
    gid = _parse_gid(gid_raw)

    if gid:
        group = get_object_or_404(Group, pk=gid)
        if not device.groups.filter(pk=group.id).exists():
            return HttpResponseForbidden("Device not in group")
        is_visible = (group.owner_id == request.user.id) or group.memberships.filter(
            user=request.user
        ).exists()
        if not is_visible:
            return HttpResponseForbidden("No permission")
    else:
        visible = device.groups.filter(
            Q(owner=request.user) | Q(memberships__user=request.user)
        ).exists()
        if not visible:
            return HttpResponseForbidden("No permission")

    # 判斷是否 AJAX/HTMX
    is_ajax = (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or request.headers.get("HX-Request") == "true"
        or "application/json" in (request.headers.get("Accept") or "")
    )

    # ===== 動作對映 =====
    kind = (cap.kind or "").strip().lower()
    act = (action or "").strip().lower()
    cmd_name = None
    payload: dict = {}

    if kind == "light":
        cmd_name = {"on": "light_on", "off": "light_off", "toggle": "light_toggle"}.get(
            act
        )
    elif "camera" in kind or kind == "cam":
        cmd_name = {
            "start": "camera_start",
            "stop": "camera_stop",
            "status": "camera_status",
        }.get(act)
    elif kind == "locker":
        cmd_name = {
            "lock": "locker_lock",
            "unlock": "locker_unlock",
            "toggle": "locker_toggle",
        }.get(act)
        # ★ 依使用者要求：locker 的 payload 指定固定 target = "main-door"
        #   這樣 Agent 會收到：
        #   - unlock: cmd=locker_unlock, payload.target=main-door
        #   - toggle: cmd=locker_toggle, payload.target=main-door
        #   - lock  : cmd=locker_lock,   payload.target=main-door（保持一致性）
        payload["target"] = "main-door"

    # 自動感光模式開關（不強制綁 kind）
    if cmd_name is None and act in ("auto_on", "auto_off"):
        cmd_name = "auto_light_on" if act == "auto_on" else "auto_light_off"
        # 可選參數：覆蓋 YAML
        for k in (
            "sensor",
            "led",
            "on_below",
            "off_above",
            "sample_every_ms",
            "require_n_samples",
        ):
            v = request.POST.get(k)
            if v not in (None, ""):
                if k in ("on_below", "off_above"):
                    try:
                        v = float(v)
                    except:
                        pass
                if k in ("sample_every_ms", "require_n_samples"):
                    try:
                        v = int(v)
                    except:
                        pass
                payload[k] = v

    if not cmd_name:
        # 不支援的動作
        err = f"Unsupported action: {action}"
        if is_ajax:
            return JsonResponse({"ok": False, "error": err}, status=400)
        messages.error(request, err)
        return redirect(request.META.get("HTTP_REFERER", reverse("home")))

    # 附上 slug（慣例）。若前面已指定 target（例如 locker=main-door），不覆蓋。
    if getattr(cap, "slug", None):
        payload.setdefault("target", cap.slug)
        payload.setdefault("slug", cap.slug)

    # 送指令
    req_id = _queue_command(device, cmd_name, payload=payload)
    
    # 發送通知給群組成員
    try:
        from notifications.services.devices import notify_device_action
        
        # 取得群組物件（如果有的話）
        group_obj = None
        if gid:
            group_obj = get_object_or_404(Group, pk=gid)
        
        # 除錯資訊
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Device action notification: device={device.id}, action={cmd_name}, actor={request.user.id}, group_id={gid}, group_obj={group_obj}")
        
        # 發送通知
        result = notify_device_action(
            device=device,
            action=cmd_name,
            actor=request.user,
            group=group_obj,
            capability_name=cap.name,
        )
        
        logger.info(f"Notification result: {len(result) if result else 0} notifications created")
        
    except Exception as e:
        # 通知失敗不影響主要功能，只記錄錯誤
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to send device action notification: {e}")
        import traceback
        logger.warning(f"Traceback: {traceback.format_exc()}")

    # 訊息字串（同時支援 AJAX 與 redirect）
    msg = {
        "on": "已送出：開燈",
        "off": "已送出：關燈",
        "toggle": "已送出：切換",
        "lock": "已送出：上鎖",
        "unlock": "已送出：開鎖",
        "auto_on": "已啟用自動",
        "auto_off": "已停用自動",
        "start": "已送出：錄影開始",
        "stop": "已送出：錄影停止",
        "status": "已查詢狀態",
    }.get(act, "已送出")

    messages.success(request, msg)

    if is_ajax:
        # 把這次 messages 取出回傳前端（前端用 toast 顯示）
        storage = get_messages(request)
        data = [{"level": m.level_tag, "message": m.message} for m in storage]
        return JsonResponse(
            {
                "ok": True,
                "req_id": req_id,
                "cap_id": cap.id,
                "action": act,
                "messages": data,
            },
            status=200,
        )

    # 非 AJAX：照舊導回
    next_url = request.POST.get("next") or request.GET.get("next")
    if not next_url:
        params = []
        if gid_raw:
            params.append(f"g={gid_raw}")
        params += [f"d={device.id}", f"cap={cap.id}"]
        next_url = reverse("home") + "?" + "&".join(params)
    return redirect(next_url)


@login_required
def live_player(request, device_id: int, cap_id: int):
    device = get_object_or_404(Device, pk=device_id)
    cap = get_object_or_404(DeviceCapability, pk=cap_id, device=device)

    # 權限：裝置需在使用者可見群組
    gid_raw = request.GET.get("group_id") or request.GET.get("g") or ""
    gid = _parse_gid(gid_raw)
    if gid:
        group = get_object_or_404(Group, pk=gid)
        in_group = device.groups.filter(pk=group.id).exists()
        visible = (group.owner_id == request.user.id) or group.memberships.filter(
            user=request.user
        ).exists()
        if not in_group or not visible:
            return HttpResponseForbidden("No permission")
    else:
        visible = device.groups.filter(
            Q(owner=request.user) | Q(memberships__user=request.user)
        ).exists()
        if not visible:
            return HttpResponseForbidden("No permission")

    cam_hls_url = request.build_absolute_uri(
        reverse("hls_proxy", args=[device.serial_number, "index.m3u8"])
    )
    ctx = {
        "device": device,
        "cap": cap,
        "group_id": gid_raw,
        "cam_hls_url": cam_hls_url,
        "csrf_token": get_token(request),
        "start_url": reverse("capability_action", args=[device.id, cap.id, "start"]),
        "stop_url": reverse("capability_action", args=[device.id, cap.id, "stop"]),
    }
    return render(request, "pi_devices/live_player.html", ctx)
