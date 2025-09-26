#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GPIO 清理腳本
釋放被占用的 GPIO 腳位
"""

import os
import sys
import time
import subprocess


def check_gpio_usage():
    """檢查 GPIO 使用情況"""
    print("🔍 檢查 GPIO 使用情況...")

    try:
        # 檢查 lsof 輸出
        result = subprocess.run(["lsof"], capture_output=True, text=True)
        gpio_lines = [
            line for line in result.stdout.split("\n") if "gpio" in line.lower()
        ]

        if gpio_lines:
            print("📋 找到 GPIO 相關程序：")
            for line in gpio_lines:
                print(f"   {line}")
        else:
            print("✅ 沒有找到 GPIO 相關程序")

    except Exception as e:
        print(f"❌ 檢查失敗: {e}")


def check_python_processes():
    """檢查 Python 程序"""
    print("\n🔍 檢查 Python 程序...")

    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        python_lines = [
            line
            for line in result.stdout.split("\n")
            if "python" in line and "grep" not in line
        ]

        if python_lines:
            print("📋 找到 Python 程序：")
            for line in python_lines:
                print(f"   {line}")
        else:
            print("✅ 沒有找到 Python 程序")

    except Exception as e:
        print(f"❌ 檢查失敗: {e}")


def check_systemd_services():
    """檢查 systemd 服務"""
    print("\n🔍 檢查 systemd 服務...")

    try:
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service"],
            capture_output=True,
            text=True,
        )
        homepi_lines = [
            line for line in result.stdout.split("\n") if "homepi" in line.lower()
        ]

        if homepi_lines:
            print("📋 找到 HomePi 服務：")
            for line in homepi_lines:
                print(f"   {line}")
        else:
            print("✅ 沒有找到 HomePi 服務")

    except Exception as e:
        print(f"❌ 檢查失敗: {e}")


def cleanup_gpio():
    """清理 GPIO"""
    print("\n🧹 清理 GPIO...")

    try:
        # 嘗試釋放 GPIO 腳位
        for pin in [18, 22, 23, 27]:
            try:
                # 嘗試釋放 GPIO 腳位
                subprocess.run(
                    ["sudo", "sh", "-c", f"echo {pin} > /sys/class/gpio/unexport"],
                    capture_output=True,
                    text=True,
                )
                print(f"   ✅ 釋放 pin {pin}")
            except:
                print(f"   ⚠️  pin {pin} 可能未被占用")

    except Exception as e:
        print(f"❌ 清理失敗: {e}")


def test_gpio_after_cleanup():
    """清理後測試 GPIO"""
    print("\n🧪 清理後測試 GPIO...")

    try:
        # 設定環境變數
        os.environ["GPIOZERO_PIN_FACTORY"] = "lgpio"

        # 測試 gpiozero
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

        print("   回到 90 度...")
        servo.angle = 90
        time.sleep(1)

        servo.detach()
        print("✅ 伺服馬達測試成功！")

        return True

    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        return False


def main():
    print("🚀 GPIO 清理腳本")
    print("=" * 50)

    # 檢查當前狀態
    check_gpio_usage()
    check_python_processes()
    check_systemd_services()

    # 清理 GPIO
    cleanup_gpio()

    # 等待一下
    print("\n⏳ 等待 2 秒...")
    time.sleep(2)

    # 測試 GPIO
    if test_gpio_after_cleanup():
        print("\n🎉 GPIO 清理成功！")
    else:
        print("\n❌ GPIO 清理失敗")
        print("\n💡 請嘗試以下解決方案：")
        print("1. 重啟樹莓派: sudo reboot")
        print("2. 檢查是否有其他程式占用 GPIO")
        print("3. 檢查硬體接線是否正確")


if __name__ == "__main__":
    main()
