#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
詳細伺服馬達測試腳本
測試不同的脈寬和角度設定
"""

import os
import sys
import time

# 設定 GPIO 工廠
os.environ["GPIOZERO_PIN_FACTORY"] = "lgpio"


def test_servo_detailed():
    """詳細測試伺服馬達"""
    print("🔧 詳細伺服馬達測試...")
    print("=" * 50)

    try:
        from gpiozero import AngularServo

        # 測試不同的脈寬設定
        servo_configs = [
            {"min_us": 500, "max_us": 2500, "name": "標準 SG90"},
            {"min_us": 400, "max_us": 2400, "name": "寬範圍"},
            {"min_us": 600, "max_us": 2600, "name": "窄範圍"},
            {"min_us": 1000, "max_us": 2000, "name": "保守設定"},
        ]

        for config in servo_configs:
            print(f"\n🔧 測試 {config['name']} 設定...")
            print(f"   脈寬範圍: {config['min_us']}us - {config['max_us']}us")

            try:
                servo = AngularServo(
                    18,
                    min_angle=0,
                    max_angle=180,
                    min_pulse_width=config["min_us"] / 1_000_000.0,
                    max_pulse_width=config["max_us"] / 1_000_000.0,
                )

                # 測試不同角度
                angles = [0, 45, 90, 135, 180]
                for angle in angles:
                    print(f"   設定到 {angle} 度...")
                    servo.angle = angle
                    time.sleep(2)  # 等待更長時間

                print(f"   ✅ {config['name']} 設定成功")
                servo.detach()

            except Exception as e:
                print(f"   ❌ {config['name']} 設定失敗: {e}")

        # 測試 PWM 頻率
        print(f"\n🔧 測試 PWM 頻率...")
        try:
            from gpiozero import PWMOutputDevice

            # 測試不同的 PWM 頻率
            frequencies = [50, 100, 200, 500]
            for freq in frequencies:
                print(f"   測試 {freq}Hz PWM...")
                pwm = PWMOutputDevice(18, frequency=freq)
                pwm.value = 0.5  # 50% 占空比
                time.sleep(1)
                pwm.off()
                pwm.close()

        except Exception as e:
            print(f"   ❌ PWM 測試失敗: {e}")

    except Exception as e:
        print(f"❌ 伺服馬達測試失敗: {e}")
        import traceback

        traceback.print_exc()


def test_servo_manual():
    """手動測試伺服馬達"""
    print("\n🔧 手動伺服馬達測試...")
    print("=" * 50)

    try:
        from gpiozero import AngularServo

        servo = AngularServo(18, min_angle=0, max_angle=180)

        print("請觀察伺服馬達是否轉動...")
        print("按 Enter 繼續到下一個角度...")

        angles = [0, 45, 90, 135, 180]
        for angle in angles:
            print(f"\n設定到 {angle} 度...")
            servo.angle = angle
            input("按 Enter 繼續...")

        servo.detach()
        print("✅ 手動測試完成")

    except Exception as e:
        print(f"❌ 手動測試失敗: {e}")


def check_hardware():
    """檢查硬體狀態"""
    print("\n🔍 檢查硬體狀態...")
    print("=" * 50)

    try:
        # 檢查 GPIO 腳位
        import subprocess

        result = subprocess.run(["gpio", "readall"], capture_output=True, text=True)
        print("GPIO 腳位狀態:")
        print(result.stdout)

        # 檢查電壓
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = int(f.read()) / 1000
                print(f"CPU 溫度: {temp}°C")
        except:
            print("無法讀取溫度")

    except Exception as e:
        print(f"❌ 硬體檢查失敗: {e}")


def main():
    print("🚀 詳細伺服馬達測試腳本")
    print("=" * 50)

    # 檢查硬體
    check_hardware()

    # 測試伺服馬達
    test_servo_detailed()

    # 手動測試
    test_servo_manual()

    print("\n🎉 測試完成！")
    print("\n💡 如果伺服馬達仍然不動，請檢查：")
    print("1. 電源供應是否足夠（5V）")
    print("2. 接線是否正確（信號線連到 pin 18）")
    print("3. 伺服馬達是否損壞")
    print("4. 脈寬設定是否適合您的伺服馬達")


if __name__ == "__main__":
    main()
