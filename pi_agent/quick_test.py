#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
電子鎖快速測試腳本
最簡單的測試方式
"""

import os
import sys
import time

# 設定 GPIO 工廠
os.environ["GPIOZERO_PIN_FACTORY"] = "lgpio"

# 添加路徑
sys.path.insert(0, os.path.dirname(__file__))


def quick_test():
    print("🔧 快速測試電子鎖...")

    try:
        # 直接測試 gpiozero
        from gpiozero import AngularServo, LED

        print("✅ gpiozero 可用")

        # 測試伺服馬達
        print("🔧 測試伺服馬達 (pin 18)...")
        servo = AngularServo(18, min_angle=0, max_angle=180)

        print("   設定到 90 度...")
        servo.angle = 90
        time.sleep(1)

        print("   設定到 0 度...")
        servo.angle = 0
        time.sleep(1)

        print("   設定到 180 度...")
        servo.angle = 180
        time.sleep(1)

        print("   回到 90 度...")
        servo.angle = 90
        time.sleep(1)

        servo.detach()
        print("✅ 伺服馬達測試完成")

        # 測試 LED
        print("🔧 測試 LED...")
        led_green = LED(23)
        led_red = LED(22)

        print("   綠燈亮...")
        led_green.on()
        led_red.off()
        time.sleep(1)

        print("   紅燈亮...")
        led_green.off()
        led_red.on()
        time.sleep(1)

        print("   全部關閉...")
        led_green.off()
        led_red.off()

        print("✅ LED 測試完成")

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    quick_test()
