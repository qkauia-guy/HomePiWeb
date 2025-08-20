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

# 啟動時先初始化 LED（沒 GPIO 也不會掛掉）
led.setup_led()

# 命令分發表
COMMANDS = {
    "light_on": led.light_on,
    "light_off": led.light_off,
    "light_toggle": led.light_toggle,
    # 之後可加更多：
    # "unlock": lock.unlock_hw,
    # "read_temp": sensor.read_temp,
}


def main():
    last_ping = 0
    while True:
        # 每 30 秒回報一次在線
        if time.time() - last_ping > 30:
            http.ping()
            last_ping = time.time()

        # 拉取下一筆待執行指令
        cmd = http.pull(max_wait=20)
        if not cmd:
            continue

        name = (cmd.get("cmd") or "").strip()
        req_id = cmd.get("req_id") or ""

        try:
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
