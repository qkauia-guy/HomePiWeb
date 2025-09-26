#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
電子鎖快速測試腳本（樹莓派專用）
嘗試不同的 GPIO 工廠
"""

import os
import sys
import time


def test_with_factory(factory_name):
    """使用指定的 GPIO 工廠測試"""
    print(f"🔧 使用 {factory_name} 工廠測試...")

    # 設定 GPIO 工廠
    os.environ["GPIOZERO_PIN_FACTORY"] = factory_name

    try:
        # 直接測試 gpiozero
        from gpiozero import AngularServo, LED

        print(f"✅ gpiozero 可用 (工廠: {factory_name})")

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
        return True

    except Exception as e:
        print(f"❌ {factory_name} 測試失敗: {e}")
        return False


def main():
    print("🔧 樹莓派 GPIO 工廠測試...")
    print("=" * 50)

    # 嘗試不同的 GPIO 工廠
    factories = ["lgpio", "rpigpio", "pigpio", "native"]

    success = False

    for factory in factories:
        print(f"\n🔄 嘗試 {factory} 工廠...")
        if test_with_factory(factory):
            print(f"✅ {factory} 工廠測試成功！")
            success = True
            break
        else:
            print(f"❌ {factory} 工廠失敗")

    if not success:
        print("\n❌ 所有 GPIO 工廠都失敗了")
        print("\n💡 請嘗試以下解決方案：")
        print("1. 安裝 lgpio: sudo apt install python3-lgpio")
        print("2. 安裝 pigpio: sudo apt install python3-pigpio")
        print("3. 檢查權限: sudo usermod -a -G gpio $USER")
        print("4. 重新登入或重啟")
    else:
        print("\n🎉 找到可用的 GPIO 工廠！")


if __name__ == "__main__":
    main()
