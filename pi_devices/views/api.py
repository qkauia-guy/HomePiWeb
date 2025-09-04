# pi_devices/views/api.py
# -*- coding: utf-8 -*-
import os
import json, time
from datetime import timedelta
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from django.utils.cache import patch_cache_control
from django.http import (
    JsonResponse,
    HttpResponse,
    Http404,
    StreamingHttpResponse,
    HttpResponseNotFound,
)
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.utils.text import slugify
import requests
from django.http import Http404
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from ..models import Device, DeviceCommand, DeviceCapability, DeviceSchedule
from notifications.services import notify_device_ip_changed, notify_user_online
from django.utils.encoding import iri_to_uri
import re
import secrets
from django.db import IntegrityError
from django.utils import timezone as djtz
from groups.models import Group
from django.views.decorators.cache import never_cache

# ---------- Helpers ----------


def _gen_req_id() -> str:
    # 16 字元十六進位，高熵且短，適配大多數 CharField 長度
    return secrets.token_hex(8)


def _queue_command(device: Device, command: str, payload: dict | None = None) -> str:
    """建一筆 pending 指令，回傳 req_id（保證在同一 device 下唯一）"""
    ttl_sec = int(
        getattr(
            settings,
            "DEVICE_COMMAND_EXPIRES_SECONDS",
            getattr(settings, "DEVICE_COMMAND_TTL_SECONDS", 30),
        )
    )
    now = timezone.now()
    expires_at = now + timedelta(seconds=ttl_sec)

    # 撞 UNIQUE(device, req_id) 就重試幾次
    for _ in range(6):
        req_id = _gen_req_id()
        try:
            cmd = DeviceCommand.objects.create(
                device=device,
                req_id=req_id,  # ← 明確指定，不依賴模型 default
                command=command,
                payload=payload or {},
                status="pending",
                created_at=now,
                expires_at=expires_at,
            )
            return cmd.req_id
        except IntegrityError:
            continue  # 罕見碰撞，換一個 req_id 再試

    # 理論上不會到這：連續多次碰撞
    raise IntegrityError("Failed to allocate unique req_id for DeviceCommand")


def sync_caps(device, caps: list[dict], auto_disable_unseen: bool = False) -> int:
    """
    依據裝置回報的 capabilities（list of dict）做 upsert：
      key = (slug)（你模型 unique_together 已是 (device, slug)）
      欄位：kind/name/config/order/enabled
    回傳：此次處理的項目數（含 create/update）
    """
    current = {c.slug: c for c in device.capabilities.all()}
    seen = set()
    changed = 0

    for item in caps:
        if not isinstance(item, dict):
            continue
        kind = (item.get("kind") or "").strip() or "light"
        name = (item.get("name") or "").strip() or kind
        slug = (item.get("slug") or slugify(name))[:50] or "cap"
        config = item.get("config") or {}
        order = int(item.get("order") or 0)
        enabled = bool(item.get("enabled", True))

        seen.add(slug)

        if slug in current:
            obj = current[slug]
            dirty = False
            if obj.kind != kind:
                obj.kind = kind
                dirty = True
            if obj.name != name:
                obj.name = name
                dirty = True
            if obj.config != config:
                obj.config = config
                dirty = True
            if obj.order != order:
                obj.order = order
                dirty = True
            if obj.enabled != enabled:
                obj.enabled = enabled
                dirty = True
            if dirty:
                obj.save()
                changed += 1
        else:
            DeviceCapability.objects.create(
                device=device,
                kind=kind,
                name=name,
                slug=slug,
                config=config,
                order=order,
                enabled=enabled,
            )
            changed += 1

    if auto_disable_unseen:
        for slug, obj in current.items():
            if slug not in seen and obj.enabled:
                obj.enabled = False
                obj.save(update_fields=["enabled"])
                changed += 1

    return changed


# ---------- APIs ----------
@csrf_exempt
@require_POST
def device_ping(request):
    body = request.body.decode("utf-8") if request.body else ""
    if not body:
        return JsonResponse({"error": "Empty body"}, status=400)
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    serial = data.get("serial_number")
    token = data.get("token")
    if not serial:
        return JsonResponse({"error": "No serial_number"}, status=400)
    if not token:
        return JsonResponse({"error": "No token"}, status=401)

    # 允許 agent 以頂層或 extra 帶更多資訊
    extra = data.get("extra") or {}
    caps = data.get("caps") or extra.get("caps")
    state_map = data.get("state") or extra.get("state")

    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    # client_ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
    client_ip = (
        xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
    ) or ""

    try:
        with transaction.atomic():
            device = (
                Device.objects.select_for_update()
                .only(
                    "id", "serial_number", "token", "ip_address", "user_id", "last_ping"
                )
                .get(serial_number=serial)
            )
            if device.token != token:
                return JsonResponse({"error": "Unauthorized"}, status=401)

            owner_id = device.user_id
            now = timezone.now()
            window = getattr(settings, "DEVICE_ONLINE_WINDOW_SECONDS", 60)
            threshold = now - timedelta(seconds=window)

            was_online = False
            if owner_id:
                was_online = bool(device.last_ping and device.last_ping >= threshold)
                if not was_online:
                    was_online = (
                        Device.objects.filter(
                            user_id=owner_id, last_ping__gte=threshold
                        )
                        .exclude(pk=device.pk)
                        .exists()
                    )

            old_ip = device.ip_address or None
            ip_changed = old_ip != client_ip

            # 更新心跳/IP
            device.last_ping = now
            device.ip_address = client_ip
            device.save(update_fields=["last_ping", "ip_address"])

            # (1) upsert capabilities（若有帶）
            if isinstance(caps, list) and caps:
                sync_caps(device, caps, auto_disable_unseen=False)

            # (2) merge 即時狀態到 cached_state（若有帶）
            if isinstance(state_map, dict) and state_map:
                # 先檢查模型是否真的有 cached_state 欄位；沒有就整段跳過（避免 500）
                try:
                    has_cached_state = any(
                        f.name == "cached_state"
                        for f in DeviceCapability._meta.get_fields()
                    )
                except Exception:
                    has_cached_state = False

                if has_cached_state:
                    slugs = list(state_map.keys())
                    if slugs:
                        cap_qs = DeviceCapability.objects.filter(
                            device=device, slug__in=slugs
                        )
                        cap_by_slug = {c.slug: c for c in cap_qs}

                        def _as_dict(v):
                            return v if isinstance(v, dict) else {}

                        for slug, st in state_map.items():
                            cap = cap_by_slug.get(slug)
                            if not cap or not isinstance(st, dict):
                                continue
                            merged = _as_dict(getattr(cap, "cached_state", {}))
                            # 嘗試淺合併；不可序列化或型別錯誤則略過該 slug
                            try:
                                merged.update({k: v for k, v in st.items()})
                            except Exception:
                                continue
                            try:
                                cap.cached_state = merged
                                cap.save(update_fields=["cached_state"])
                            except Exception:
                                # 欄位存在但 DB 層出錯（例如 migration 未套用），也不要讓整個 ping 失敗
                                pass
                else:
                    # 欄位不存在：什麼都不做（避免 500）
                    pass

            # 上線/變更 IP 通知（照原邏輯）
            if owner_id and not was_online:
                from django.contrib.auth import get_user_model

                User = get_user_model()
                subject_user = User.objects.filter(pk=owner_id).first()
                if subject_user:
                    transaction.on_commit(lambda: notify_user_online(user=subject_user))

            if ip_changed and owner_id:
                transaction.on_commit(
                    lambda: notify_device_ip_changed(
                        device=device,
                        owner=device.user,  # 允許 lazy load
                        old_ip=old_ip,
                        new_ip=client_ip,
                    )
                )

    except Device.DoesNotExist:
        return JsonResponse({"error": "Device not found"}, status=404)
    except Exception as e:
        return JsonResponse(
            {"error": f"server error: {type(e).__name__}: {e}"}, status=500
        )

    # 回傳 pong 與目前 IP
    return JsonResponse({"status": "pong", "ip": client_ip})


@csrf_exempt
@require_POST
def device_pull(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    serial = data.get("serial_number")
    token = data.get("token")
    max_wait = int(
        data.get("max_wait") or getattr(settings, "DEVICE_COMMAND_MAX_WAIT_SECONDS", 20)
    )
    if not serial or not token:
        return JsonResponse({"error": "serial_number/token required"}, status=400)

    try:
        device = Device.objects.only("id", "serial_number", "token").get(
            serial_number=serial
        )
    except Device.DoesNotExist:
        return JsonResponse({"error": "Device not found"}, status=404)
    if device.token != token:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    deadline = time.time() + max_wait
    while True:
        with transaction.atomic():
            now = timezone.now()
            DeviceCommand.objects.filter(
                device=device, status="pending", expires_at__lte=now
            ).update(status="expired")
            cmd = (
                DeviceCommand.objects.select_for_update(skip_locked=True)
                .filter(device=device, status="pending", expires_at__gt=now)
                .order_by("created_at")
                .first()
            )
            if cmd:
                cmd.status = "taken"
                cmd.taken_at = now
                cmd.save(update_fields=["status", "taken_at"])
                return JsonResponse(
                    {"cmd": cmd.command, "req_id": cmd.req_id, "payload": cmd.payload}
                )
        if time.time() >= deadline:
            return HttpResponse(status=204)
        time.sleep(0.2)


@csrf_exempt
@require_POST
def device_ack(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    serial = data.get("serial_number")
    token = data.get("token")
    req_id = data.get("req_id")
    ok = bool(data.get("ok"))
    error = data.get("error") or ""
    state_map = data.get("state")  # ★ agent 可帶回即時 state

    if not serial or not token or not req_id:
        return JsonResponse(
            {"error": "serial_number/token/req_id required"}, status=400
        )

    try:
        device = Device.objects.only("id", "serial_number", "token").get(
            serial_number=serial
        )
    except Device.DoesNotExist:
        return JsonResponse({"error": "Device not found"}, status=404)
    if device.token != token:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    from django.utils import timezone as djtz

    with transaction.atomic():
        # 更新指令狀態
        cmd = (
            DeviceCommand.objects.select_for_update()
            .filter(device=device, req_id=req_id)
            .first()
        )
        if cmd and cmd.status not in ("done", "failed", "expired"):
            cmd.status = "done" if ok else "failed"
            cmd.error = "" if ok else (error or "unknown")
            cmd.done_at = djtz.now()
            cmd.save(update_fields=["status", "error", "done_at"])

        # ★ 立刻 merge 回報的狀態：{ '<slug>': {...} }
        if isinstance(state_map, dict) and state_map:
            slugs = list(state_map.keys())
            caps = DeviceCapability.objects.filter(device=device, slug__in=slugs)
            by_slug = {c.slug: c for c in caps}
            for slug, st in state_map.items():
                cap = by_slug.get(slug)
                if not cap or not isinstance(st, dict):
                    continue
                merged = (cap.cached_state or {}).copy()
                merged.update(st)  # 直接覆蓋同名 key
                cap.cached_state = merged
                cap.save(update_fields=["cached_state"])

    return JsonResponse({"ok": True})


# ---------- Camera control (live stream) ----------
@csrf_exempt
@require_POST
def camera_action(request, serial: str, action: str):
    """後端按鈕用：排入 camera_start / camera_stop 指令，允許帶 camera slug。"""
    try:
        device = Device.objects.get(serial_number=serial)
    except Device.DoesNotExist:
        return JsonResponse({"error": "Device not found"}, status=404)

    if action not in ("start", "stop"):
        return JsonResponse({"error": "bad action"}, status=400)

    # 嘗試解析 JSON 以取得 slug（可選）
    slug = None
    if request.body:
        try:
            payload_in = json.loads(request.body.decode("utf-8"))
            slug = (payload_in or {}).get("slug")
        except Exception:
            pass

    cmd_name = "camera_start" if action == "start" else "camera_stop"
    req_id = _queue_command(device, cmd_name, payload={"slug": slug} if slug else {})
    return JsonResponse({"ok": True, "req_id": req_id, "cmd": cmd_name})


@require_GET
def camera_status(request, serial: str):
    """
    提供前端播放網址（以該裝置最近 ping 的 IP 推算 HLS 來源）。
    """
    try:
        device = Device.objects.only("ip_address").get(serial_number=serial)
    except Device.DoesNotExist:
        return JsonResponse({"error": "Device not found"}, status=404)

    ip = device.ip_address or ""
    hls_url = f"http://{ip}:8088/index.m3u8" if ip else ""
    return JsonResponse({"ok": True, "ip": ip, "hls_url": hls_url})


# 代理 /hls/<serial>/<path> 到樹莓派 8088
SESSION = requests.Session()
TIMEOUT = (3, 15)  # connect, read


def _device_hls_base(device: Device, cap: DeviceCapability):
    cfg = cap.config or {}
    host = (cfg.get("hls_host") or "").strip() or (device.ip_address or "127.0.0.1")
    port = int(cfg.get("hls_port") or 8088)
    # 樹梅派 http_hls.py chdir 到 stream 目錄，索引與片段都在根目錄
    base = f"http://{host}:{port}"
    return base


def _rewrite_m3u8(body: str, serial: str) -> str:
    # 把相對路徑的 .ts 片段改成 /hls/<serial>/seg_xxx.ts
    def repl(line: str) -> str:
        line = line.strip()
        if not line or line.startswith("#"):
            return line
        if line.startswith("http://") or line.startswith("https://"):
            return line  # 已是絕對路徑就不動
        if line.startswith("/hls/"):
            return line  # 已被改寫過
        if line.endswith(".ts"):
            return f"/hls/{serial}/{line}"
        return line

    return "\n".join(repl(l) for l in body.splitlines())


@csrf_exempt
@require_http_methods(["GET", "HEAD"])
def hls_proxy(request, serial: str, subpath: str):
    device = (
        Device.objects.filter(serial_number__iexact=serial).only("ip_address").first()
    )
    if not device or not device.ip_address:
        return HttpResponseNotFound("device ip not found")

    base = f"http://{device.ip_address}:8088"

    # ---- Playlist (.m3u8) ----
    if subpath.endswith(".m3u8"):
        upstream = f"{base}/{iri_to_uri(os.path.basename(subpath))}"
        try:
            r = requests.get(
                upstream,
                timeout=(3, 10),
                allow_redirects=False,
                headers={"Accept-Encoding": "identity"},
            )
        except requests.RequestException:
            resp = HttpResponse("m3u8 upstream error", status=502)
            resp["X-HLS-Proxy"] = "1"
            resp["X-Upstream-Status"] = "CONN_ERR"
            return resp

        body_bytes = r.content or b""
        try:
            body_text = body_bytes.decode(r.encoding or "utf-8", "replace")
        except Exception:
            body_text = body_bytes.decode("utf-8", "replace")

        if r.status_code != 200 or not body_text.strip():
            resp = HttpResponse("m3u8 upstream error", status=502)
            resp["X-HLS-Proxy"] = "1"
            resp["X-Upstream-Status"] = str(r.status_code)
            resp["X-Upstream-Len"] = str(len(body_bytes))
            return resp

        def rewrite(line: str) -> str:
            t = line.strip()
            if not t or t.startswith("#"):
                return line
            if t.endswith(".ts"):
                name = os.path.basename(t)
                return f"/hls/{serial}/{name}"
            return line

        out = "\n".join(rewrite(ln) for ln in body_text.splitlines()) + "\n"
        resp = HttpResponse(out, content_type="application/vnd.apple.mpegurl")
        resp["Cache-Control"] = "no-store"
        resp["X-Accel-Buffering"] = "no"
        resp["X-HLS-Proxy"] = "1"
        resp["X-Upstream-Status"] = str(r.status_code)
        resp["X-Upstream-Len"] = str(len(body_bytes))
        resp["Content-Length"] = str(len(out.encode("utf-8")))
        return resp

    # ---- Segment (.ts)：保持你原來的處理，另外加上 X-HLS-Proxy ----
    name = os.path.basename(subpath)
    if not name.endswith(".ts"):
        return HttpResponseNotFound("only ts allowed")

    upstream = f"{base}/{iri_to_uri(name)}"
    fwd_headers = {}
    rng = request.headers.get("Range")
    if rng:
        fwd_headers["Range"] = rng
    fwd_headers["Accept-Encoding"] = "identity"

    try:
        r = requests.request(
            request.method,
            upstream,
            headers=fwd_headers,
            stream=True,
            timeout=(3, 20),
            allow_redirects=False,
        )
    except requests.RequestException:
        return HttpResponseNotFound("upstream error")

    if r.status_code in (200, 206):
        ct = r.headers.get("Content-Type", "video/mp2t")
        if request.method == "HEAD":
            resp = HttpResponse(status=r.status_code, content_type=ct)
        else:
            resp = StreamingHttpResponse(
                r.iter_content(64 * 1024), status=r.status_code, content_type=ct
            )
        for h in (
            "Content-Length",
            "Content-Range",
            "Accept-Ranges",
            "Last-Modified",
            "ETag",
        ):
            if h in r.headers:
                resp[h] = r.headers[h]
        resp["Cache-Control"] = "no-store"
        resp["X-Accel-Buffering"] = "no"
        resp["X-HLS-Proxy"] = "1"
        return resp

    if r.status_code == 416:
        resp = HttpResponse(status=416)
        if "Content-Range" in r.headers:
            resp["Content-Range"] = r.headers["Content-Range"]
        return resp

    if r.status_code == 404:
        return HttpResponseNotFound("ts not found")

    resp = HttpResponse("upstream error", status=502)
    resp["X-Upstream-Status"] = str(r.status_code)
    resp["X-HLS-Proxy"] = "1"
    return resp


# 狀態連動


def _parse_gid(raw: str | None) -> int | None:
    if not raw:
        return None
    s = raw.strip()
    if s.startswith("g") and s[1:].isdigit():
        return int(s[1:])
    if s.isdigit():
        return int(s)
    return None


@never_cache
@login_required
def api_cap_status(request, cap_id: int):
    cap = get_object_or_404(
        DeviceCapability.objects.select_related("device"), pk=cap_id
    )

    gid_raw = request.GET.get("group_id") or request.GET.get("g") or ""
    gid = _parse_gid(gid_raw)
    if gid:
        group = get_object_or_404(Group, pk=gid)
        if not cap.device.groups.filter(pk=group.id).exists():
            return HttpResponseForbidden("Device not in group")
        is_visible = (group.owner_id == request.user.id) or group.memberships.filter(
            user=request.user
        ).exists()
        if not is_visible:
            return HttpResponseForbidden("No permission")
    else:
        visible = cap.device.groups.filter(
            Q(owner=request.user) | Q(memberships__user=request.user)
        ).exists()
        if not visible:
            return HttpResponseForbidden("No permission")

    st = cap.cached_state or {}
    light_is_on = bool(st.get("light_is_on", False))
    auto_running = bool(st.get("auto_light_running", False))
    last_lux = st.get("last_lux", None)
    last_change_ts = st.get("last_change_ts", None)

    # last_change_ts 可能是 float/datetime/None，把它標準化成 epoch 秒（int）
    if hasattr(last_change_ts, "timestamp"):  # datetime-like
        try:
            last_change_ts = int(last_change_ts.timestamp())
        except Exception:
            last_change_ts = None
    elif isinstance(last_change_ts, (int, float)):
        last_change_ts = int(last_change_ts)
    else:
        last_change_ts = None

    # 是否有相關指令尚未完成（用 slug 過濾）
    now = timezone.now()
    pending = DeviceCommand.objects.filter(
        device=cap.device,
        status__in=["pending", "taken"],
        expires_at__gt=now,
        payload__slug=cap.slug,
    ).exists()

    resp = JsonResponse(
        {
            "ok": True,
            "light_is_on": light_is_on,
            "auto_light_running": auto_running,
            "last_lux": last_lux,
            "pending": pending,
            "last_change_ts": last_change_ts,
            "server_ts": int(timezone.now().timestamp()),
        }
    )
    resp["Cache-Control"] = "no-store"
    return resp


def _auth_device(data):
    serial = data.get("serial_number")
    token = data.get("token")
    if not serial or not token:
        return None, JsonResponse({"error": "serial_number/token required"}, status=400)
    try:
        dev = Device.objects.only("id", "token").get(serial_number=serial)
    except Device.DoesNotExist:
        return None, JsonResponse({"error": "Device not found"}, status=404)
    if dev.token != token:
        return None, JsonResponse({"error": "Unauthorized"}, status=401)
    return dev, None


@csrf_exempt
@require_POST
def device_schedules(request):
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    device, err = _auth_device(data)
    if err:
        return err

    now = timezone.now()
    # 只給未執行的未來排程（容忍 2 分鐘的時鐘漂移：>= now-120s）
    qs = DeviceSchedule.objects.filter(
        device=device, status="pending", run_at__gte=now - timedelta(seconds=120)
    ).order_by("run_at")[:100]

    items = []
    for s in qs:
        items.append(
            {
                "id": s.id,
                "action": s.action,
                "payload": s.payload or {},
                # 用 epoch 秒，樹梅派好處理
                "ts": int(s.run_at.timestamp()),
            }
        )

    return JsonResponse({"ok": True, "items": items})


@csrf_exempt
@require_POST
def device_schedule_ack(request):
    # 解析 JSON
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    # 驗證裝置身分
    device, err = _auth_device(data)
    if err:
        return err

    try:
        sid = data.get("schedule_id")
        if sid is None:
            return JsonResponse({"error": "schedule_id required"}, status=400)
        try:
            sid = int(sid)
        except (TypeError, ValueError):
            return JsonResponse({"error": "bad schedule_id"}, status=400)

        ok = bool(data.get("ok"))
        error = data.get("error") or ""

        # 交易內鎖 row → 更新狀態
        with transaction.atomic():
            s = (
                DeviceSchedule.objects.select_for_update()
                .filter(id=sid, device=device)
                .first()
            )
            if not s:
                return JsonResponse({"error": "Schedule not found"}, status=404)

            if s.status != "pending":
                # 已處理過就當作成功
                return JsonResponse({"ok": True})

            s.status = "done" if ok else "failed"
            s.error = "" if ok else (error[:500])  # 避免過長
            s.done_at = timezone.now()
            s.save(update_fields=["status", "error", "done_at"])

        return JsonResponse({"ok": True})

    except Exception as e:
        # 暫時把錯誤丟回前端，方便你在 Network 面板直接看到原因
        return JsonResponse(
            {"error": f"server error: {type(e).__name__}: {e}"}, status=500
        )
