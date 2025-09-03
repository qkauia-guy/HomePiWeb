# -*- coding: utf-8 -*-
"""
http_agent.py
- 主程式：處理「指令分發」與「心跳上報」
- 硬體控制：devices/
- HTTP API：utils/http.py
- YAML：config/loader.py
- 自動感光：utils/auto_light.py（支援 auto_light_on / auto_light_off，且在狀態變化時立即回推 state）
"""

import os
import time
from copy import deepcopy

# === 設定載入與能力偵測 ===
from config.loader import load as load_config
from detect.registry import discover_all

# === HTTP 封裝（ping / pull / ack） ===
from utils import http

# 先讀 YAML
CFG = load_config() or {}

# 設定 gpiozero PinFactory（若 YAML 沒寫則沿用環境或預設 lgpio）
os.environ["GPIOZERO_PIN_FACTORY"] = CFG.get(
    "gpio_factory", os.environ.get("GPIOZERO_PIN_FACTORY", "lgpio")
)

# ❗ 在設定好 PinFactory 後再載入硬體模組
from devices import led
from devices import camera

# 自動感光 + 即時回推 callback
from utils.auto_light import (
    start_auto_light,
    stop_auto_light,
    set_state_push,
    get_state as auto_state,
)

# === 命令分發表 ===
COMMANDS = {
    "light_on": led.light_on,
    "light_off": led.light_off,
    "light_toggle": led.light_toggle,
    "camera_start": camera.start_hls,
    "camera_stop": camera.stop_hls,
}

# === 全域暫存（給 callback 用）===
_LAST_LIGHT_SLUG: str | None = None
_CAPS_SNAPSHOT = None


def _call_handler(handler, cmd: dict):
    target = cmd.get("target") or cmd.get("name")
    try:
        if target is not None:
            return handler(target)
    except TypeError:
        pass
    return handler()


# === 狀態回報小工具 ===
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
        }
    }


def _build_state_blob(caps):
    slug = _first_light_slug(caps)
    return _state_for_slug(slug)


def _push_state_from_auto():
    """給 auto_light 註冊的回呼：燈狀態真的切換時立刻回推 state。"""
    slug = _LAST_LIGHT_SLUG or _first_light_slug(_CAPS_SNAPSHOT)
    if not slug:
        return
    try:
        http.ping(extra={"state": _state_for_slug(slug)})
    except Exception as e:
        print("[auto_light] push state ping err:", e)


def main():
    global _CAPS_SNAPSHOT, _LAST_LIGHT_SLUG

    # === 硬體初始化 ===
    try:
        led.setup_led(CFG)
    except Exception as e:
        print("[WARN] led.setup_led 失敗：", e)

    last_ping = 0.0
    caps = None
    first_caps_sent = False

    # === 開機做一次能力偵測 ===
    try:
        caps = discover_all()
        _CAPS_SNAPSHOT = caps
        print("discovered caps:", caps)
    except Exception as e:
        print("[WARN] discover_all 失敗：", e)

    # === 主迴圈 ===
    while True:
        # 週期性心跳（附帶目前 state；首次也帶 caps）
        if time.time() - last_ping > 30:
            try:
                extra = {"state": _build_state_blob(caps)}
                if caps and not first_caps_sent:
                    extra["caps"] = caps
                if http.ping(extra=extra):
                    if "caps" in extra:
                        first_caps_sent = True
            except Exception as e:
                print("[WARN] ping 失敗：", e)
            last_ping = time.time()

        # 長輪詢取指令
        try:
            cmd = http.pull(max_wait=20)
        except Exception as e:
            print("[WARN] pull 失敗：", e)
            time.sleep(1.0)
            continue

        if not cmd:
            continue

        name = (cmd.get("cmd") or "").strip()
        req_id = cmd.get("req_id") or ""
        payload = cmd.get("payload") or {}

        try:
            # 重新偵測能力
            if name == "rescan_caps":
                try:
                    caps = discover_all()
                    _CAPS_SNAPSHOT = caps
                    http.ping(extra={"caps": caps, "state": _build_state_blob(caps)})
                    slug = payload.get("slug") or _first_light_slug(caps)
                    # 更新我們的預設 slug
                    _LAST_LIGHT_SLUG = slug or _LAST_LIGHT_SLUG
                    http.ack(req_id, ok=True, state=_state_for_slug(slug))
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

                # 確保 LED
                try:
                    if not led.list_leds():
                        led.setup_led(merged)
                except Exception:
                    led.setup_led(merged)

                # 設定 slug 與即時回推 callback
                _LAST_LIGHT_SLUG = payload.get("slug") or _first_light_slug(caps)
                set_state_push(_push_state_from_auto)

                start_auto_light(merged)
                # 立即 ack 一次目前狀態（啟動/warm-up 讀值）
                http.ack(req_id, ok=True, state=_state_for_slug(_LAST_LIGHT_SLUG))
                continue

            # 自動感光：停用
            if name == "auto_light_off":
                # 取消 callback（避免之後誤觸發）
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
