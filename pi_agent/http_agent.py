# -*- coding: utf-8 -*-
"""
http_agent.py
- 主程式：指令分發 / 心跳上報 / 本地排程
- 硬體控制：devices/
- HTTP API：utils/http.py
- YAML：config/loader.py
- 自動感光：utils/auto_light.py（支援 auto_light_on / auto_light_off）
"""
import os
import time
from copy import deepcopy

# === 設定載入與能力偵測 ===
from config.loader import load as load_config
from detect.registry import discover_all

# === HTTP 封裝（ping / pull / ack） ===
from utils import http

# 自動感光背景執行緒（BH1750 -> LED）
from utils.auto_light import (
    start_auto_light,
    stop_auto_light,
    get_state as auto_state,
    set_state_push,
)

# 本地排程器
from utils.scheduler import LocalScheduler

import psutil
import subprocess

# 先讀 YAML
CFG = load_config() or {}

# 設定 gpiozero PinFactory（若 YAML 沒寫則沿用環境或預設 lgpio）
os.environ["GPIOZERO_PIN_FACTORY"] = CFG.get(
    "gpio_factory", os.environ.get("GPIOZERO_PIN_FACTORY", "lgpio")
)

# ❗ 在設定好 PinFactory 後再載入硬體模組
from devices import led
from devices import camera
from devices import locker

from utils.metrics import get_pi_metrics

# === 命令分發表 ===
COMMANDS = {
    "light_on": led.light_on,
    "light_off": led.light_off,
    "light_toggle": led.light_toggle,
    "camera_start": camera.start_hls,
    "camera_stop": camera.stop_hls,
    "locker_lock": locker.lock,
    "locker_unlock": locker.unlock,
    "locker_toggle": locker.toggle,
}

# === 全域快取 ===
_CAPS_SNAPSHOT = None
_LAST_LIGHT_SLUG = None


def _call_handler(handler, cmd: dict):
    payload = cmd.get("payload") or {}
    target = payload.get("target")
    try:
        if target is not None:
            return handler(target)
    except TypeError:
        pass
    return handler()


def _first_light_slug(caps):
    if not caps:
        return None
    for c in caps:
        try:
            if str(c.get("kind", "")).lower() == "light" and c.get("slug"):
                return c["slug"]
        except Exception:
            continue
    return None


def _state_for_slug(slug: str | None) -> dict:
    if not slug:
        return {}
    try:
        st = auto_state() or {}
    except Exception:
        st = {}
    try:
        led_on = bool(led.is_on())
    except Exception:
        led_on = False
    return {
        slug: {
            "auto_light_running": bool(st.get("running")),
            "light_is_on": led_on,
            "last_lux": st.get("last_lux"),
            "last_change_ts": st.get("last_change_ts"),
        }
    }


def _build_state_blob(caps):
    state = {}

    # light 狀態
    slug = _first_light_slug(caps)
    if slug:
        state.update(_state_for_slug(slug))

    # locker 狀態
    try:
        names = list((locker.list_lockers() or {}).keys())
        for n in names:
            state[n] = locker.get_state(n)
    except Exception as e:
        print("[WARN] 取 locker 狀態失敗：", e)

    return state


def _push_state_from_auto():
    """auto_light 狀態改變時 push"""
    global _LAST_LIGHT_SLUG, _CAPS_SNAPSHOT
    slug = _LAST_LIGHT_SLUG or _first_light_slug(_CAPS_SNAPSHOT)
    if not slug:
        return
    try:
        http.ping(extra={"state": _state_for_slug(slug)})
    except Exception as e:
        print("[auto_light] push state err:", e)


def _push_state_from_locker():
    """電子鎖狀態改變時 push"""
    print("[DEBUG] _push_state_from_locker 開始執行")
    try:
        names = list((locker.list_lockers() or {}).keys())
        print(f"[DEBUG] _push_state_from_locker 取得 locker 清單: {names}")
    except Exception as e:
        print(f"[DEBUG] _push_state_from_locker 取得 locker 清單失敗: {e}")
        names = []
    if not names:
        print("[DEBUG] _push_state_from_locker 沒有 locker，跳過")
        return
    try:
        print(f"[DEBUG] _push_state_from_locker 開始取得狀態")
        state = {}
        for n in names:
            try:
                print(f"[DEBUG] _push_state_from_locker 取得 {n} 狀態")
                state[n] = locker.get_state(n)
                print(f"[DEBUG] _push_state_from_locker {n} 狀態: {state[n]}")
            except Exception as e:
                print(f"[DEBUG] _push_state_from_locker 取得 {n} 狀態失敗: {e}")
                state[n] = {"locked": False, "auto_lock_running": False, "name": n}
        
        print(f"[DEBUG] _push_state_from_locker 準備發送 ping，state: {state}")
        http.ping(extra={"state": state})
        print("[DEBUG] _push_state_from_locker ping 發送完成")
        print("[DEBUG] _push_state_from_locker triggered:", state)
    except Exception as e:
        print(f"[DEBUG] _push_state_from_locker ping 發送失敗: {e}")
        print("[locker] push state err:", e)


def run_action(action: str, payload: dict | None = None):
    """本地排程器執行函式"""
    global _LAST_LIGHT_SLUG, _CAPS_SNAPSHOT

    payload = payload or {}
    name = action.strip()
    if name in ("auto_light_on", "auto_light_off"):
        if name == "auto_light_on":
            merged = deepcopy(CFG)
            merged.setdefault("auto_light", {})
            merged["auto_light"]["enabled"] = True
            for k in (
                "sensor",
                "led",
                "on_below",
                "off_above",
                "sample_every_ms",
                "require_n_samples",
            ):
                if k in payload:
                    merged["auto_light"][k] = payload[k]
            try:
                if not led.list_leds():
                    led.setup_led(merged)
            except Exception:
                led.setup_led(merged)

            _LAST_LIGHT_SLUG = (
                payload.get("slug")
                or _LAST_LIGHT_SLUG
                or _first_light_slug(_CAPS_SNAPSHOT)
            )
            set_state_push(_push_state_from_auto)
            try:
                stop_auto_light(wait=True)
            except Exception:
                pass
            start_auto_light(merged)
        else:
            set_state_push(None)
            stop_auto_light(wait=True)
            led_name = payload.get("led") or (CFG.get("auto_light", {}) or {}).get(
                "led"
            )
            try:
                if led_name:
                    led.light_off(led_name)
                else:
                    for k in list(led.list_leds().keys()):
                        led.light_off(k)
            except Exception as e:
                print("[auto_light] 停用關燈失敗：", e)

    else:
        handler = COMMANDS.get(name)
        if handler:
            try:
                target = payload.get("target") or payload.get("name")
                if target is not None:
                    handler(target)
                else:
                    handler()
            except TypeError:
                handler()
        else:
            print(f"[sched] unknown action: {name}")
            return

    slug = payload.get("slug") or _LAST_LIGHT_SLUG or _first_light_slug(_CAPS_SNAPSHOT)
    if slug:
        try:
            http.ping(extra={"state": _state_for_slug(slug)})
        except Exception as e:
            print("[sched] push state err:", e)


def main():
    global _CAPS_SNAPSHOT, _LAST_LIGHT_SLUG

    # === 初始化 ===
    try:
        led.setup_led(CFG)
    except Exception as e:
        print("[WARN] led.setup_led 失敗：", e)

    try:
        locker.setup_locker(CFG)  # ✅ 只在這裡初始化一次
    except Exception as e:
        print("[WARN] locker.setup_locker 失敗：", e)

    try:
        locker.set_state_push(_push_state_from_locker)
    except Exception as e:
        print("[WARN] locker.set_state_push 失敗：", e)

    # === 掃描能力 ===
    caps = None
    try:
        caps = discover_all()
        _CAPS_SNAPSHOT = caps
        _LAST_LIGHT_SLUG = _first_light_slug(caps)
        print("discovered caps:", caps)
    except Exception as e:
        print("[WARN] discover_all 失敗：", e)

    # === 啟動排程器 ===
    scheduler = LocalScheduler(run_action)
    try:
        scheduler.start()
        scheduler.refresh_from_server()
    except Exception as e:
        print("[sched] init err:", e)

    # === 主迴圈 ===
    last_ping = 0.0
    last_sched_refresh = 0.0

    while True:
        now = time.time()

        if now - last_ping > 30:
            try:
                extra = {
                    "state": _build_state_blob(caps),
                    "metrics": get_pi_metrics(),
                }
                if _CAPS_SNAPSHOT:
                    extra["caps"] = _CAPS_SNAPSHOT
                http.ping(extra=extra)
            except Exception as e:
                print("[WARN] ping 失敗：", e)
            last_ping = now

        if now - last_sched_refresh > 10:
            try:
                scheduler.refresh_from_server()
            except Exception as e:
                print("[sched] refresh err:", e)
            last_sched_refresh = now

        try:
            cmd = http.pull(max_wait=8)
        except Exception as e:
            print("[WARN] pull 失敗：", e)
            time.sleep(0.5)
            continue

        if not cmd:
            time.sleep(0.1)
            continue

        name = (cmd.get("cmd") or "").strip()
        req_id = cmd.get("req_id") or ""
        payload = cmd.get("payload") or {}

        try:
            if name == "rescan_caps":
                try:
                    caps = discover_all()
                    _CAPS_SNAPSHOT = caps
                    _LAST_LIGHT_SLUG = _first_light_slug(caps) or _LAST_LIGHT_SLUG
                    http.ping(extra={"caps": caps, "state": _build_state_blob(caps)})
                    http.ack(req_id, ok=True, state=_state_for_slug(_LAST_LIGHT_SLUG))
                except Exception as e:
                    http.ack(req_id, ok=False, error=str(e))
                continue

            if name == "auto_light_on":
                merged = deepcopy(CFG)
                merged.setdefault("auto_light", {})
                merged["auto_light"]["enabled"] = True
                for k in (
                    "sensor",
                    "led",
                    "on_below",
                    "off_above",
                    "sample_every_ms",
                    "require_n_samples",
                ):
                    if k in payload:
                        merged["auto_light"][k] = payload[k]
                try:
                    if not led.list_leds():
                        led.setup_led(merged)
                except Exception:
                    led.setup_led(merged)

                _LAST_LIGHT_SLUG = (
                    payload.get("slug") or _LAST_LIGHT_SLUG or _first_light_slug(caps)
                )
                set_state_push(_push_state_from_auto)
                try:
                    stop_auto_light(wait=True)
                except Exception:
                    pass
                start_auto_light(merged)

                http.ack(req_id, ok=True, state=_state_for_slug(_LAST_LIGHT_SLUG))
                continue

            if name == "auto_light_off":
                set_state_push(None)
                stop_auto_light(wait=True)
                led_name = payload.get("led") or (CFG.get("auto_light", {}) or {}).get(
                    "led"
                )
                try:
                    if led_name:
                        led.light_off(led_name)
                        print(f"[auto_light] 已停用，自動關燈 {led_name}")
                    else:
                        for k in list(led.list_leds().keys()):
                            led.light_off(k)
                        print("[auto_light] 已停用，未指定 LED，已嘗試關閉所有 LED")
                except Exception as e:
                    print("[auto_light] 停用時關燈失敗：", e)

                slug = (
                    payload.get("slug") or _LAST_LIGHT_SLUG or _first_light_slug(caps)
                )
                http.ack(req_id, ok=True, state=_state_for_slug(slug))
                continue

            handler = COMMANDS.get(name)
            if handler is None:
                http.ack(req_id, ok=False, error=f"unknown command: {name}")
                continue

            # 先處理 locker 指令的 debug 和 ack
            if name in ("locker_lock", "locker_unlock", "locker_toggle"):
                print(f"[DEBUG] 處理 locker 指令: {name}, req_id: {req_id}")
                target = payload.get("target")
                slug = payload.get("slug")
                print(f"[DEBUG] target: {target}, slug: {slug}")
                
                if not slug:
                    try:
                        names = list((locker.list_lockers() or {}).keys())
                        slug = names[0] if names else None
                        print(f"[DEBUG] 自動取得 slug: {slug}")
                    except Exception as e:
                        print(f"[DEBUG] 取得 locker 清單失敗: {e}")
                        slug = None
                
                if not slug:
                    print(f"[DEBUG] 準備發送 ack (失敗): req_id={req_id}, error=missing slug")
                    http.ack(
                        req_id, ok=False, error="missing slug and no locker available"
                    )
                    print(f"[DEBUG] ack 已發送 (失敗)")
                    continue
                
                # 執行硬體操作
                print(f"[DEBUG] 準備執行硬體操作: {name}")
                _call_handler(handler, cmd)
                print(f"[DEBUG] 硬體操作完成: {name}")
                
                print(f"[DEBUG] 取得 locker 狀態: slug={slug}")
                state = locker.get_state(slug)
                print(f"[DEBUG] locker 狀態: {state}")
                
                print(f"[DEBUG] 準備發送 ack (成功): req_id={req_id}, state={slug}: {state}")
                http.ack(req_id, ok=True, state={slug: state})
                print(f"[DEBUG] ack 已發送 (成功)")
                continue

            # 執行其他指令
            _call_handler(handler, cmd)

            if name in ("light_on", "light_off", "light_toggle"):
                slug = (
                    payload.get("slug") or _LAST_LIGHT_SLUG or _first_light_slug(caps)
                )
                http.ack(req_id, ok=True, state=_state_for_slug(slug))

        except Exception as e:
            try:
                http.ack(req_id, ok=False, error=str(e))
            except Exception:
                print("[ERROR] ack 失敗：", e)


def get_pi_metrics():
    """取得樹莓派運行狀況"""
    metrics = {}
    try:
        metrics["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        metrics["memory_percent"] = psutil.virtual_memory().percent
        temp = None
        try:
            output = subprocess.check_output(
                ["vcgencmd", "measure_temp"], encoding="utf-8"
            )
            temp = float(output.replace("temp=", "").replace("'C", "").strip())
        except Exception:
            temps = psutil.sensors_temperatures()
            if "cpu-thermal" in temps:
                temp = temps["cpu-thermal"][0].current
        if temp is not None:
            metrics["temperature"] = temp
    except Exception as e:
        print(f"[WARN] get_pi_metrics failed: {e}")
    return metrics


if __name__ == "__main__":
    main()
