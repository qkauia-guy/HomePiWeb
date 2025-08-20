# -*- coding: utf-8 -*-
"""
http_agent.py
- 主程式：專心處理指令分發
- 硬體控制：devices/
- HTTP API：utils/http.py
"""

import time
from devices import led
from utils import http
from detect.registry import discover_all  # ✅ 加上偵測匯入

# 命令分發表（指令名 -> 處理函式）
COMMANDS = {
    "light_on": led.light_on,
    "light_off": led.light_off,
    "light_toggle": led.light_toggle,
    # 之後可加更多：
    # "unlock": lock.unlock_hw,
    # "read_temp": sensor.read_temp,
}


def main():
    # 硬體初始化（GPIO 不可用時不會掛）
    led.setup_led()

    last_ping = 0
    caps = None
    first_caps_sent = False

    # ✅ 開機做一次功能偵測（模板 + 自動偵測）
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

            handler()  # 執行對應硬體操作
            http.ack(req_id, ok=True)

        except Exception as e:
            http.ack(req_id, ok=False, error=str(e))


if __name__ == "__main__":
    main()
