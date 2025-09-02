# -*- coding: utf-8 -*-
"""
http_agent.py
- 主程式：專心處理「指令分發」與「心跳上報」
- 硬體控制：devices/
- HTTP API：utils/http.py
- YAML 載入：config/loader.py
- 自動感光：utils/auto_light.py（支援 auto_light_on / auto_light_off 指令）
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

# 自動感光背景執行緒（BH1750 -> LED）
from utils.auto_light import start_auto_light, stop_auto_light


# 命令分發表（指令名 -> 處理函式）
# 備註：為相容舊的「不帶目標」用法，_call_handler 會嘗試把 target/name 傳入，失敗則呼叫無參數版。
COMMANDS = {
    "light_on": led.light_on,
    "light_off": led.light_off,
    "light_toggle": led.light_toggle,
    "camera_start": camera.start_hls,
    "camera_stop": camera.stop_hls,
    # 之後可加更多：
    # "unlock": lock.unlock_hw,
    # "read_temp": sensor.read_temp,
}


def _call_handler(handler, cmd: dict):
    """
    嘗試把 command 裡的 target/name 交給 handler，如果不支援參數就退回無參數呼叫。
    讓 {"cmd": "light_on", "target": "led_2"} 可以控制指定裝置，
    同時相容舊版（不帶 target/name）。
    """
    target = cmd.get("target") or cmd.get("name")
    try:
        if target is not None:
            return handler(target)
    except TypeError:
        # handler 不吃參數 → 走舊版無參數呼叫
        pass
    return handler()


def main():
    # === 硬體初始化 ===
    # LED 會依 YAML 初始化（若無 YAML 定義則 fallback 環境變數/預設 pin）
    try:
        led.setup_led(CFG)
    except Exception as e:
        print("[WARN] led.setup_led 失敗：", e)

    last_ping = 0.0
    caps = None
    first_caps_sent = False

    # === 開機做一次能力偵測（模板 + 自動偵測）===
    try:
        caps = discover_all()
        print("discovered caps:", caps)
    except Exception as e:
        print("[WARN] discover_all 失敗：", e)

    # === 主迴圈 ===
    while True:
        # 週期性心跳；第一次夾帶 caps 讓後端 upsert 能力清單
        if time.time() - last_ping > 30:
            extra = {"caps": caps} if (caps and not first_caps_sent) else None
            try:
                if http.ping(extra=extra):
                    if extra:
                        first_caps_sent = True
            except Exception as e:
                print("[WARN] ping 失敗：", e)
            last_ping = time.time()

        # 長輪詢取指令
        try:
            cmd = http.pull(max_wait=20)
        except Exception as e:
            print("[WARN] pull 失敗：", e)
            # 稍等一下避免過度打擾伺服器
            time.sleep(1.0)
            continue

        if not cmd:
            # 超時（204）或目前無指令
            continue

        name = (cmd.get("cmd") or "").strip()
        req_id = cmd.get("req_id") or ""
        payload = cmd.get("payload") or {}

        try:
            # === 重新偵測能力 ===
            if name == "rescan_caps":
                try:
                    caps = discover_all()
                    # 立刻回報一次最新能力
                    http.ping(extra={"caps": caps})
                    http.ack(req_id, ok=True)
                except Exception as e:
                    http.ack(req_id, ok=False, error=str(e))
                continue

            # === 自動感光：啟動 ===
            if name == "auto_light_on":
                merged = deepcopy(CFG)
                merged.setdefault("auto_light", {})
                merged["auto_light"]["enabled"] = True

                # 允許覆蓋 YAML 預設（前端不傳就用 YAML）
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

                # 確保 LED 已初始化（通常 main 開頭已做，這裡再保險檢查）
                try:
                    if not led.list_leds():
                        led.setup_led(merged)
                except Exception:
                    led.setup_led(merged)

                start_auto_light(merged)
                http.ack(req_id, ok=True)
                continue

            # === 自動感光：停用 ===
            if name == "auto_light_off":
                stop_auto_light()
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
                http.ack(req_id, ok=True)
                continue

            # === 其餘交給分發表 ===
            handler = COMMANDS.get(name)
            if handler is None:
                http.ack(req_id, ok=False, error=f"unknown command: {name}")
                continue

            _call_handler(handler, cmd)
            http.ack(req_id, ok=True)

        except Exception as e:
            # 任一指令處理錯誤都要 ack 失敗，避免重複消費
            try:
                http.ack(req_id, ok=False, error=str(e))
            except Exception as _:
                # 若 ack 也失敗，就寫 log 但仍持續迴圈
                print("[ERROR] ack 失敗：", e)


if __name__ == "__main__":
    main()
