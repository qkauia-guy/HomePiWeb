#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地環境測試腳本
在 macOS 上測試電子鎖邏輯，不依賴硬體
"""

import os
import sys
import time
from pathlib import Path

# 添加 pi_agent 目錄到 Python 路徑
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))


def test_locker_logic_local():
    """測試電子鎖邏輯（本地環境，不依賴硬體）"""
    print("🔧 測試電子鎖邏輯（本地環境）...")
    print("=" * 50)

    try:
        # 匯入電子鎖模組
        from devices import locker

        print("✅ 成功匯入 locker 模組")

        # 手動設定配置（模擬 YAML 設定）
        mock_config = {
            "devices": [
                {
                    "name": "main-door",
                    "kind": "locker",
                    "config": {
                        "button_pin": 27,
                        "servo_pin": 18,
                        "led_green": 23,
                        "led_red": 22,
                        "auto_lock_delay": 10,
                    },
                }
            ]
        }

        print("✅ 使用模擬設定檔")

        # 初始化電子鎖（會進入 no-op 模式）
        print("\n🔧 初始化電子鎖...")
        locker.setup_locker(mock_config)

        # 列出所有電子鎖
        lockers = locker.list_lockers()
        print(f"📋 發現的電子鎖: {lockers}")

        if not lockers:
            print("❌ 沒有找到電子鎖")
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

        # 測試自動上鎖功能
        print(f"\n⏰ 測試自動上鎖功能...")
        locker.unlock(locker_name)
        print("   已開鎖，等待 3 秒檢查自動上鎖...")

        for i in range(3):
            time.sleep(1)
            state = locker.get_state(locker_name)
            print(
                f"   {i+1}秒後狀態: {state.get('locked', 'Unknown')} (自動上鎖: {state.get('auto_lock_running', 'Unknown')})"
            )

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


def test_config_parsing():
    """測試設定檔解析"""
    print("\n🔧 測試設定檔解析...")
    print("=" * 50)

    try:
        # 讀取 YAML 檔案
        yaml_path = Path(__file__).parent / "config" / "homepi.yml"

        if yaml_path.exists():
            print(f"✅ 找到設定檔: {yaml_path}")

            # 手動解析 YAML（不依賴 yaml 模組）
            with open(yaml_path, "r", encoding="utf-8") as f:
                content = f.read()

            print(f"📋 檔案大小: {len(content)} 字元")

            # 簡單檢查電子鎖設定
            if "kind: locker" in content:
                print("✅ 找到電子鎖設定")

                # 提取 pin 設定
                lines = content.split("\n")
                for i, line in enumerate(lines):
                    if "servo_pin:" in line:
                        pin = line.split(":")[1].strip()
                        print(f"   伺服馬達腳位: {pin}")
                    elif "led_green:" in line:
                        pin = line.split(":")[1].strip()
                        print(f"   綠燈腳位: {pin}")
                    elif "led_red:" in line:
                        pin = line.split(":")[1].strip()
                        print(f"   紅燈腳位: {pin}")
                    elif "button_pin:" in line:
                        pin = line.split(":")[1].strip()
                        print(f"   按鈕腳位: {pin}")
            else:
                print("❌ 沒有找到電子鎖設定")
        else:
            print(f"❌ 設定檔不存在: {yaml_path}")

    except Exception as e:
        print(f"❌ 設定檔解析失敗: {e}")


def test_module_structure():
    """測試模組結構"""
    print("\n🔧 測試模組結構...")
    print("=" * 50)

    try:
        # 檢查 devices 模組
        from devices import locker, led, camera

        print("✅ devices 模組匯入成功")

        # 檢查 utils 模組
        from utils import http, scheduler, metrics

        print("✅ utils 模組匯入成功")

        # 檢查 config 模組
        from config import loader

        print("✅ config 模組匯入成功")

        # 檢查 detect 模組
        from detect import registry

        print("✅ detect 模組匯入成功")

        print("✅ 所有模組結構正常")

    except Exception as e:
        print(f"❌ 模組結構測試失敗: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    print("🚀 本地環境測試腳本")
    print("=" * 50)

    # 檢查環境
    print(f"🖥️  作業系統: {os.name}")
    print(f"🐍 Python 版本: {sys.version}")
    print(f"📁 工作目錄: {os.getcwd()}")
    print(f"📁 腳本目錄: {Path(__file__).parent}")

    # 執行測試
    test_module_structure()
    test_config_parsing()
    test_locker_logic_local()

    print("\n🎉 本地測試完成！")
    print("\n💡 提示：")
    print("   - 此測試在本地環境執行，不依賴硬體")
    print("   - 要測試硬體功能，請在樹莓派上執行：")
    print("     ssh qkauia.pie")
    print("     cd /path/to/HomePiWeb/pi_agent")
    print("     python3 quick_test.py")
