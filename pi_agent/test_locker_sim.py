#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
電子鎖模擬測試腳本
在沒有硬體的環境中測試電子鎖邏輯
"""

import os
import sys
import time
from pathlib import Path

# 添加 pi_agent 目錄到 Python 路徑
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))


def test_locker_logic():
    """測試電子鎖邏輯（不依賴硬體）"""
    print("🔧 測試電子鎖邏輯...")
    print("=" * 50)

    try:
        # 匯入電子鎖模組
        from devices import locker

        print("✅ 成功匯入 locker 模組")

        # 載入設定
        from config.loader import load

        cfg = load()
        print(f"✅ 成功載入設定檔")

        # 初始化電子鎖（會進入 no-op 模式）
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
        print(f"   名稱: {state.get('name', 'Unknown')}")

        # 測試開鎖
        print(f"\n🔓 測試開鎖...")
        locker.unlock(locker_name)
        time.sleep(1)

        state = locker.get_state(locker_name)
        print(f"   開鎖後狀態: {state.get('locked', 'Unknown')}")
        print(f"   自動上鎖運行中: {state.get('auto_lock_running', 'Unknown')}")

        # 測試上鎖
        print(f"\n🔒 測試上鎖...")
        locker.lock(locker_name)
        time.sleep(1)

        state = locker.get_state(locker_name)
        print(f"   上鎖後狀態: {state.get('locked', 'Unknown')}")
        print(f"   自動上鎖運行中: {state.get('auto_lock_running', 'Unknown')}")

        # 測試切換
        print(f"\n🔄 測試切換...")
        locker.toggle(locker_name)
        time.sleep(1)

        state = locker.get_state(locker_name)
        print(f"   切換後狀態: {state.get('locked', 'Unknown')}")
        print(f"   自動上鎖運行中: {state.get('auto_lock_running', 'Unknown')}")

        # 測試 is_locked 函數
        print(f"\n🔍 測試 is_locked 函數...")
        is_locked = locker.is_locked(locker_name)
        print(f"   is_locked 結果: {is_locked}")

        print(f"\n✅ 電子鎖邏輯測試完成！")

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


def test_config_loading():
    """測試設定檔載入"""
    print("\n🔧 測試設定檔載入...")
    print("=" * 50)

    try:
        from config.loader import load

        cfg = load()

        print(f"✅ 設定檔載入成功")
        print(f"📋 GPIO 工廠: {cfg.get('gpio_factory', '未設定')}")

        devices = cfg.get("devices", [])
        print(f"📋 裝置數量: {len(devices)}")

        for i, device in enumerate(devices):
            if device.get("kind") == "locker":
                print(f"   🔒 電子鎖 {i+1}: {device.get('name', '未命名')}")
                config = device.get("config", {})
                print(f"      按鈕腳位: {config.get('button_pin', '未設定')}")
                print(f"      伺服腳位: {config.get('servo_pin', '未設定')}")
                print(f"      綠燈腳位: {config.get('led_green', '未設定')}")
                print(f"      紅燈腳位: {config.get('led_red', '未設定')}")
                print(
                    f"      自動上鎖延遲: {config.get('auto_lock_delay', '未設定')}秒"
                )

        auto_light = cfg.get("auto_light", {})
        if auto_light:
            print(f"💡 自動感光設定:")
            print(f"      感應器: {auto_light.get('sensor', '未設定')}")
            print(f"      LED: {auto_light.get('led', '未設定')}")
            print(f"      開燈閾值: {auto_light.get('on_below', '未設定')} lx")
            print(f"      關燈閾值: {auto_light.get('off_above', '未設定')} lx")

    except Exception as e:
        print(f"❌ 設定檔測試失敗: {e}")
        import traceback

        traceback.print_exc()


def test_yaml_parsing():
    """測試 YAML 解析"""
    print("\n🔧 測試 YAML 解析...")
    print("=" * 50)

    try:
        import yaml

        yaml_path = Path(__file__).parent / "config" / "homepi.yml"

        if yaml_path.exists():
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            print(f"✅ YAML 檔案解析成功")
            print(f"📋 檔案路徑: {yaml_path}")
            print(f"📋 檔案大小: {yaml_path.stat().st_size} bytes")

            # 檢查電子鎖設定
            devices = data.get("devices", [])
            locker_devices = [d for d in devices if d.get("kind") == "locker"]

            if locker_devices:
                print(f"🔒 找到 {len(locker_devices)} 個電子鎖設定")
                for i, locker in enumerate(locker_devices):
                    print(f"   電子鎖 {i+1}: {locker.get('name', '未命名')}")
            else:
                print("❌ 沒有找到電子鎖設定")
        else:
            print(f"❌ YAML 檔案不存在: {yaml_path}")

    except Exception as e:
        print(f"❌ YAML 解析失敗: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 電子鎖模擬測試腳本")
    print("=" * 50)

    # 檢查環境
    print(f"🖥️  作業系統: {os.name}")
    print(f"🐍 Python 版本: {sys.version}")
    print(f"📁 工作目錄: {os.getcwd()}")
    print(f"📁 腳本目錄: {Path(__file__).parent}")

    # 執行測試
    test_yaml_parsing()
    test_config_loading()
    test_locker_logic()

    print("\n🎉 模擬測試完成！")
    print("\n💡 提示：")
    print("   - 在樹莓派上安裝 gpiozero: pip3 install gpiozero")
    print("   - 然後執行 python3 test_locker.py 進行硬體測試")
    print("   - 或執行 python3 quick_test.py 進行快速硬體測試")
