# -*- coding: utf-8 -*-
"""
http_agent.py
- 主程式：專心處理指令分發
- 硬體控制：devices/
- HTTP API：utils/http.py
"""

import os
import time
from utils import http
from detect.registry import discover_all

# ✅ 新增：讀取設定
from config.loader import load as load_config

CFG = load_config()

# 設定 gpiozero PinFactory（若 YAML 沒寫則保留原設定或預設 lgpio）
os.environ["GPIOZERO_PIN_FACTORY"] = CFG.get(
    "gpio_factory", os.environ.get("GPIOZERO_PIN_FACTORY", "lgpio")
)

# ❗ 在設定好 PinFactory 後再載入硬體模組
from devices import led
from devices import camera

# 命令分發表（指令名 -> 處理函式）
# 備註：為了相容舊的「不帶目標」用法，下面會用一個小 wrapper 嘗試帶 target，失敗就呼叫無參數版
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
    這讓未來可以傳 {"cmd": "light_on", "target": "led_2"} 控制指定裝置，
    但舊的簡單版（不帶 target）也仍然可用。
    """
    target = cmd.get("target") or cmd.get("name")  # name/target 二擇一都支援
    try:
        if target is not None:
            return handler(target)
    except TypeError:
        # handler 不吃參數 → 走舊版無參數呼叫
        pass
    return handler()


def main():
    # 硬體初始化：把 YAML 丟進去，讓裝置依設定建立
    #    （devices/led 會自動 fallback 到舊的環境變數/預設 pin）
    led.setup_led(CFG)

    last_ping = 0
    caps = None
    first_caps_sent = False

    # 開機做一次功能偵測（模板 + 自動偵測）
    try:
        caps = discover_all()
        print("discovered caps:", caps)
    except Exception as e:
        print("[WARN] discover_all failed:", e)

    while True:
        # 每 30 秒送心跳；第一次夾帶 caps 讓後端 upsert
        if time.time() - last_ping > 30:
            extra = {"caps": caps} if (caps and not first_caps_sent) else None
            if http.ping(extra=extra):  # ✅ 用 utils.http.ping
                if extra:
                    first_caps_sent = True
            last_ping = time.time()

        # 長輪詢取指令
        cmd = http.pull(max_wait=20)  # ✅ 用 utils.http.pull
        if not cmd:
            continue

        name = (cmd.get("cmd") or "").strip()
        req_id = cmd.get("req_id") or ""

        try:
            # （可選）支援重新偵測指令
            if name == "rescan_caps":
                try:
                    caps = discover_all()
                    http.ping(extra={"caps": caps})  # 立刻回報一次
                    http.ack(req_id, ok=True)
                except Exception as e:
                    http.ack(req_id, ok=False, error=str(e))
                continue

            handler = COMMANDS.get(name)
            if handler is None:
                http.ack(req_id, ok=False, error=f"unknown command: {name}")
                continue

            _call_handler(handler, cmd)  # ← 相容帶/不帶 target 的呼叫
            http.ack(req_id, ok=True)

        except Exception as e:
            http.ack(req_id, ok=False, error=str(e))


if __name__ == "__main__":
    main()
