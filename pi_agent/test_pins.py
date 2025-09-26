#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
測試不同 GPIO 腳位
"""

import os
import sys
import time

# 設定 GPIO 工廠
os.environ["GPIOZERO_PIN_FACTORY"] = "lgpio"


def test_pin(pin):
    """測試指定腳位"""
    print(f"🔧 測試 GPIO {pin}...")

    try:
        from gpiozero import AngularServo

        servo = AngularServo(pin, min_angle=0, max_angle=180)

        print(f"   設定到 0 度...")
        servo.angle = 0
        time.sleep(2)

        print(f"   設定到 90 度...")
        servo.angle = 90
        time.sleep(2)

        print(f"   設定到 180 度...")
        servo.angle = 180
        time.sleep(2)

        servo.detach()
        print(f"   ✅ GPIO {pin} 測試完成")
        return True

    except Exception as e:
        print(f"   ❌ GPIO {pin} 測試失敗: {e}")
        return False


def test_led_pins():
    """測試 LED 腳位"""
    print("🔧 測試 LED 腳位...")

    try:
        from gpiozero import LED

        # 測試綠燈
        print("   測試綠燈 (pin 23)...")
        led_green = LED(23)
        led_green.on()
        time.sleep(1)
        led_green.off()
        print("   ✅ 綠燈測試完成")

        # 測試紅燈
        print("   測試紅燈 (pin 22)...")
        led_red = LED(22)
        led_red.on()
        time.sleep(1)
        led_red.off()
        print("   ✅ 紅燈測試完成")

    except Exception as e:
        print(f"   ❌ LED 測試失敗: {e}")


def main():
    print("🚀 GPIO 腳位測試腳本")
    print("=" * 50)

    # 測試 LED
    test_led_pins()

    # 測試不同的 GPIO 腳位
    pins_to_test = [18, 19, 20, 21, 26, 13, 6, 5]

    for pin in pins_to_test:
        test_pin(pin)
        print()

    print("🎉 測試完成！")
    print("\n💡 如果所有腳位都沒有反應，請檢查：")
    print("1. 伺服馬達電源是否正確連接（5V）")
    print("2. 伺服馬達是否損壞")
    print("3. 接線是否牢固")
    print("4. 嘗試更換伺服馬達")


if __name__ == "__main__":
    main()
