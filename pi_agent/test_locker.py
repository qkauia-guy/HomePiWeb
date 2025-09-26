#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
電子鎖獨立測試腳本
在樹莓派上直接執行，測試電子鎖硬體功能
"""

import os
import sys
import time
from pathlib import Path

# 添加 pi_agent 目錄到 Python 路徑
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# 設定 GPIO 工廠（使用 lgpio）
os.environ["GPIOZERO_PIN_FACTORY"] = "lgpio"


def test_locker():
    """測試電子鎖功能"""
    print("🔧 開始測試電子鎖功能...")
    print("=" * 50)

    try:
        # 匯入電子鎖模組
        from devices import locker

        print("✅ 成功匯入 locker 模組")

        # 載入設定
        from config.loader import load

        cfg = load()
        print(f"✅ 成功載入設定檔")

        # 初始化電子鎖
        print("\n🔧 初始化電子鎖...")
        locker.setup_locker(cfg)

        # 列出所有電子鎖
        lockers = locker.list_lockers()
        print(f"📋 發現的電子鎖: {lockers}")

        if not lockers:
            print("❌ 沒有找到電子鎖，請檢查設定檔")
            return

        # 取得第一個電子鎖的名稱
        locker_name = list(lockers.keys())[0]
        print(f"🎯 使用電子鎖: {locker_name}")

        # 測試狀態查詢
        print(f"\n📊 初始狀態:")
        state = locker.get_state(locker_name)
        print(f"   上鎖狀態: {state.get('locked', 'Unknown')}")
        print(f"   自動上鎖運行中: {state.get('auto_lock_running', 'Unknown')}")

        # 測試開鎖
        print(f"\n🔓 測試開鎖...")
        locker.unlock(locker_name)
        time.sleep(2)

        state = locker.get_state(locker_name)
        print(f"   開鎖後狀態: {state.get('locked', 'Unknown')}")

        # 測試上鎖
        print(f"\n🔒 測試上鎖...")
        locker.lock(locker_name)
        time.sleep(2)

        state = locker.get_state(locker_name)
        print(f"   上鎖後狀態: {state.get('locked', 'Unknown')}")

        # 測試切換
        print(f"\n🔄 測試切換...")
        locker.toggle(locker_name)
        time.sleep(2)

        state = locker.get_state(locker_name)
        print(f"   切換後狀態: {state.get('locked', 'Unknown')}")

        # 測試自動上鎖（短延遲）
        print(f"\n⏰ 測試自動上鎖（5秒延遲）...")
        locker.unlock(locker_name)
        print("   已開鎖，等待 5 秒自動上鎖...")

        for i in range(5):
            time.sleep(1)
            state = locker.get_state(locker_name)
            print(
                f"   {i+1}秒後狀態: {state.get('locked', 'Unknown')} (自動上鎖: {state.get('auto_lock_running', 'Unknown')})"
            )

        print(f"\n✅ 電子鎖測試完成！")

    except ImportError as e:
        print(f"❌ 匯入錯誤: {e}")
        print("請確認 gpiozero 已安裝: pip install gpiozero")
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # 清理資源
        try:
            locker.close_all()
            print("🧹 已清理電子鎖資源")
        except:
            pass


def test_hardware_detection():
    """測試硬體偵測"""
    print("\n🔍 測試硬體偵測...")
    print("=" * 50)

    try:
        # 測試 gpiozero 是否可用
        from gpiozero import AngularServo, LED, Button

        print("✅ gpiozero 模組可用")

        # 測試 GPIO 腳位
        print("\n🔌 測試 GPIO 腳位...")

        # 測試 LED
        try:
            led = LED(23)
            led.on()
            print("✅ LED (pin 23) 測試成功")
            led.off()
        except Exception as e:
            print(f"❌ LED (pin 23) 測試失敗: {e}")

        # 測試伺服馬達
        try:
            servo = AngularServo(18, min_angle=0, max_angle=180)
            servo.angle = 90
            print("✅ 伺服馬達 (pin 18) 測試成功")
            servo.detach()
        except Exception as e:
            print(f"❌ 伺服馬達 (pin 18) 測試失敗: {e}")

        # 測試按鈕
        try:
            button = Button(27)
            print("✅ 按鈕 (pin 27) 測試成功")
        except Exception as e:
            print(f"❌ 按鈕 (pin 27) 測試失敗: {e}")

    except ImportError as e:
        print(f"❌ gpiozero 不可用: {e}")
        print("請安裝: pip install gpiozero")


if __name__ == "__main__":
    print("🚀 電子鎖獨立測試腳本")
    print("=" * 50)

    # 檢查是否在樹莓派上
    try:
        with open("/proc/cpuinfo", "r") as f:
            if "BCM" in f.read():
                print("✅ 檢測到樹莓派硬體")
            else:
                print("⚠️  未檢測到樹莓派硬體，可能無法測試硬體功能")
    except:
        print("⚠️  無法檢測硬體類型")

    # 執行測試
    test_hardware_detection()
    test_locker()

    print("\n🎉 測試完成！")
