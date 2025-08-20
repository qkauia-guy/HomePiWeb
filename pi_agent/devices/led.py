# -*- coding: utf-8 -*-
"""
LED 控制模組（devices/led.py）
- 把 GPIO 相關初始化與操作獨立出來，http_agent 只需呼叫函式。
- 透過環境變數設定腳位與極性：
    LED_PIN（預設 17）、LED_ACTIVE_HIGH（預設 true）
- 在沒有 gpiozero 或非樹莓派環境時，會自動進入 no-op（僅印訊息）。
"""
import os

# 讀環境變數
LED_PIN = int(os.getenv("LED_PIN", "17"))
LED_ACTIVE_HIGH = os.getenv("LED_ACTIVE_HIGH", "true").lower() in ("1", "true", "yes")

_led = None  # 內部 LED 物件（可能為 None → no-op）


def setup_led():
    """嘗試初始化 gpiozero.LED，失敗則進入 no-op 模式。"""
    global _led
    try:
        from gpiozero import LED  # 延遲載入，避免在非 Pi 環境報錯

        _led = LED(LED_PIN, active_high=LED_ACTIVE_HIGH)
        print(f"[LED] init ok (pin={LED_PIN}, active_high={LED_ACTIVE_HIGH})")
    except Exception as e:
        _led = None
        print("[WARN] gpiozero LED init failed:", e, "(no-op mode)")


def light_on():
    if _led:
        _led.on()
    else:
        print("[LED] on (no-op)")


def light_off():
    if _led:
        _led.off()
    else:
        print("[LED] off (no-op)")


def light_toggle():
    if _led:
        _led.toggle()
    else:
        print("[LED] toggle (no-op)")
