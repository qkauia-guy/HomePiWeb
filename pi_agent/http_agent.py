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

# 本地排程器（你自己的 utils.scheduler.LocalScheduler）
from utils.scheduler import LocalScheduler  # 需已建立此模組

# 先讀 YAML
CFG = load_config() or {}

# 設定 gpiozero PinFactory（若 YAML 沒寫則沿用環境或預設 lgpio）
os.environ["GPIOZERO_PIN_FACTORY"] = CFG.get(
    "gpio_factory", os.environ.get("GPIOZERO_PIN_FACTORY", "lgpio")
)

# ❗ 在設定好 PinFactory 後再載入硬體模組
from devices import led
from devices import camera

# === 命令分發表 ===
COMMANDS = {
    "light_on": led.light_on,
    "light_off": led.light_off,
    "light_toggle": led.light_toggle,
    "camera_start": camera.start_hls,
    "camera_stop": camera.stop_hls,
}

# === 全域快取 ===
_CAPS_SNAPSHOT = None
_LAST_LIGHT_SLUG = None


def _call_handler(handler, cmd: dict):
    """嘗試把 target/name 交給 handler，若不支援就走無參數。"""
    target = cmd.get("target") or cmd.get("name")
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
    slug = _first_light_slug(caps)
    return _state_for_slug(slug)


def _push_state_from_auto():
    """
    提供給 auto_light 的即時回推 callback（在亮度觸發 on/off 時呼叫）。
    將當前狀態推到伺服器（走 ping），讓 UI 幾秒內更新，而不是等 30s 心跳。
    """
    global _LAST_LIGHT_SLUG, _CAPS_SNAPSHOT
    slug = _LAST_LIGHT_SLUG or _first_light_slug(_CAPS_SNAPSHOT)
    if not slug:
        return
    try:
        http.ping(extra={"state": _state_for_slug(slug)})
    except Exception as e:
        print("[auto_light] push state err:", e)


def run_action(action: str, payload: dict | None = None):
    """
    本地排程器的執行函式。
    支援：light_on/light_off/light_toggle/auto_light_on/auto_light_off
    執行後主動 push state，讓 UI 快速更新。
    """
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
            # 確保 LED 初始化
            try:
                if not led.list_leds():
                    led.setup_led(merged)
            except Exception:
                led.setup_led(merged)

            # 設定即時 state push
            _LAST_LIGHT_SLUG = (
                payload.get("slug")
                or _LAST_LIGHT_SLUG
                or _first_light_slug(_CAPS_SNAPSHOT)
            )
            set_state_push(_push_state_from_auto)

            # ★ 先停舊的，再開新的（避免多執行緒與舊參數殘留）
            try:
                stop_auto_light(wait=True)
            except Exception:
                pass
            start_auto_light(merged)

        else:  # auto_light_off
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

    # 執行完主動推一次 state
    slug = payload.get("slug") or _LAST_LIGHT_SLUG or _first_light_slug(_CAPS_SNAPSHOT)
    if slug:
        try:
            http.ping(extra={"state": _state_for_slug(slug)})
        except Exception as e:
            print("[sched] push state err:", e)


def main():
    global _CAPS_SNAPSHOT, _LAST_LIGHT_SLUG

    # === 硬體初始化 ===
    try:
        led.setup_led(CFG)
    except Exception as e:
        print("[WARN] led.setup_led 失敗：", e)

    # === 掃描能力（一次即可） ===
    caps = None
    try:
        caps = discover_all()
        _CAPS_SNAPSHOT = caps
        _LAST_LIGHT_SLUG = _first_light_slug(caps)
        print("discovered caps:", caps)
    except Exception as e:
        print("[WARN] discover_all 失敗：", e)

    # === 啟動排程器（只啟動一次） ===
    scheduler = LocalScheduler(run_action)
    try:
        scheduler.start()
        scheduler.refresh_from_server()  # 開始先抓一次排程
    except Exception as e:
        print("[sched] init err:", e)

    # === 迴圈節拍 ===
    last_ping = 0.0
    last_sched_refresh = 0.0

    while True:
        now = time.time()

        # 心跳（每 30 秒，夾帶目前 state；首次也會帶 caps）
        if now - last_ping > 30:
            try:
                extra = {"state": _build_state_blob(caps)}
                # 首次帶 caps，後續不帶
                if _CAPS_SNAPSHOT is not None and last_ping == 0.0:
                    extra["caps"] = _CAPS_SNAPSHOT
                http.ping(extra=extra)
            except Exception as e:
                print("[WARN] ping 失敗：", e)
            last_ping = now

        # 排程清單刷新（預設 10 秒，可視需要調整）
        if now - last_sched_refresh > 10:
            try:
                scheduler.refresh_from_server()
            except Exception as e:
                print("[sched] refresh err:", e)
            last_sched_refresh = now

        # 【移除】不再呼叫 scheduler.run_due()，因為 LocalScheduler 自己有內部執行緒處理到點任務
        # try:
        #     scheduler.run_due()
        # except Exception as e:
        #     print("[sched] run_due err:", e)

        # 拉一筆指令（非阻塞太久，避免影響 UI 即時性）
        try:
            cmd = http.pull(max_wait=8)
        except Exception as e:
            print("[WARN] pull 失敗：", e)
            time.sleep(0.5)
            continue

        if not cmd:
            # 什麼都沒有就小睡一下，避免空轉
            time.sleep(0.1)
            continue

        # === 收到指令 ===
        name = (cmd.get("cmd") or "").strip()
        req_id = cmd.get("req_id") or ""
        payload = cmd.get("payload") or {}

        try:
            # 重新偵測能力
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

            # 自動感光：啟動
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

                # 確保 LED 初始化
                try:
                    if not led.list_leds():
                        led.setup_led(merged)
                except Exception:
                    led.setup_led(merged)

                # 設定 slug 與即時回推 callback
                _LAST_LIGHT_SLUG = (
                    payload.get("slug") or _LAST_LIGHT_SLUG or _first_light_slug(caps)
                )
                set_state_push(_push_state_from_auto)

                # ★ 先停再開，確保只有一個執行緒且採用最新參數
                try:
                    stop_auto_light(wait=True)
                except Exception:
                    pass
                start_auto_light(merged)

                http.ack(req_id, ok=True, state=_state_for_slug(_LAST_LIGHT_SLUG))
                continue

            # 自動感光：停用
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

            # 其餘指令（含手動燈控）
            handler = COMMANDS.get(name)
            if handler is None:
                http.ack(req_id, ok=False, error=f"unknown command: {name}")
                continue

            _call_handler(handler, cmd)

            if name in ("light_on", "light_off", "light_toggle"):
                slug = (
                    payload.get("slug") or _LAST_LIGHT_SLUG or _first_light_slug(caps)
                )
                http.ack(req_id, ok=True, state=_state_for_slug(slug))
            else:
                http.ack(req_id, ok=True)

        except Exception as e:
            try:
                http.ack(req_id, ok=False, error=str(e))
            except Exception:
                print("[ERROR] ack 失敗：", e)


if __name__ == "__main__":
    main()
