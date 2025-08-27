# -*- coding: utf-8 -*-
"""
LED 控制模組（devices/led.py）
- 優先讀取 YAML 設定（HOMEPI_CONFIG 或 ./config/homepi.yml）
- YAML 可定義多顆 LED；若沒有 YAML，則回退到環境變數：
    LED_PIN（預設 17）、LED_ACTIVE_HIGH（預設 true）
- 舊介面相容：light_on()/light_off()/light_toggle() 不帶參數會操作第一顆
- 非樹莓派或缺少 gpiozero 時，進入 no-op（只印訊息）
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Optional

# 盡早嘗試載入 gpiozero；失敗則進入 no-op
try:
    from gpiozero import LED  # type: ignore
except Exception as _e:
    LED = None  # type: ignore
    _GPIO_ERR = _e
else:
    _GPIO_ERR = None

# 內部狀態
_LEDS: Dict[str, "LED"] = {}
_DEFAULT_NAME = "led_1"  # 不帶參數時操作的預設名稱


# === 小工具 ===
def _to_bool(val, default=True) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")


def _load_yaml_config() -> dict:
    """
    嘗試載入 YAML 設定：
      1) $HOMEPI_CONFIG 指向的檔案
      2) 專案內 ./config/homepi.yml
    補充：若系統未安裝 pyyaml，或檔案不存在，回傳 {}。
    """
    # 1) 環境變數指定
    cfg_path = os.environ.get("HOMEPI_CONFIG")
    cand = None
    if cfg_path:
        cand = Path(cfg_path)
    else:
        # 2) 專案內 ./config/homepi.yml  （devices/ 的上一層就是專案根）
        cand = Path(__file__).resolve().parent.parent / "config" / "homepi.yml"

    try:
        import yaml  # type: ignore
    except Exception:
        return {}

    if cand and cand.is_file():
        try:
            with open(cand, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"[LED] YAML 讀取失敗：{e}")

    return {}


def _pick(name: Optional[str]):
    """根據名稱挑一顆 LED；若未傳或不存在，就拿第一顆；若沒有任何 LED → 例外。"""
    if name and name in _LEDS:
        return _LEDS[name]
    if _LEDS:
        # 第一顆（建立順序）
        return next(iter(_LEDS.values()))
    raise RuntimeError("No LED initialized. Did you call setup_led()?")


# === 對外 API ===
def setup_led(cfg: Optional[dict] = None):
    """
    建立多顆 LED：
      - 若 cfg 省略：自動嘗試讀取 YAML；若無 YAML → 回退環境變數（單顆）
      - 若有 YAML：devices: [ {name, kind: led, pin, active_high}, ... ]
      - 若沒有 gpiozero：no-op（只印出動作）
    """
    global _LEDS

    # 先清空（避免重複呼叫造成殘留）
    for led in _LEDS.values():
        try:
            led.close()
        except Exception:
            pass
    _LEDS.clear()

    # 讀設定
    cfg = cfg or _load_yaml_config()
    gpio_factory = cfg.get("gpio_factory")
    if gpio_factory and "GPIOZERO_PIN_FACTORY" not in os.environ:
        os.environ["GPIOZERO_PIN_FACTORY"] = str(gpio_factory)

    # 如果沒有 gpiozero，就 no-op
    if LED is None:
        print("[WARN] gpiozero 不可用：", _GPIO_ERR, "（LED 進入 no-op 模式）")

        # 就算 no-op，也解析一下 YAML 以便後續印出名稱提示
        devices = [d for d in cfg.get("devices", []) if d.get("kind") == "led"]
        if devices:
            names = [d.get("name") or _DEFAULT_NAME for d in devices]
            print(f"[LED] 已從 YAML 解析到 LED：{names}（no-op）")
        else:
            # YAML 沒有 → 嘗試環境變數
            pin = int(os.getenv("LED_PIN", "17"))
            active_high = _to_bool(os.getenv("LED_ACTIVE_HIGH", "true"))
            print(
                f"[LED] 使用環境變數（單顆）：pin={pin}, active_high={active_high}（no-op）"
            )
        return

    # 有 gpiozero：真的建立 LED
    devices = [d for d in cfg.get("devices", []) if d.get("kind") == "led"]
    if devices:
        for i, d in enumerate(devices):
            name = str(d.get("name") or (i == 0 and _DEFAULT_NAME) or f"led_{i+1}")
            pin = int(d["pin"])
            active_high = _to_bool(d.get("active_high"), True)
            _LEDS[name] = LED(pin, active_high=active_high)
            print(f"[LED] init ok: {name} (pin={pin}, active_high={active_high})")
    else:
        # YAML 沒有 → fallback 環境變數（單顆）
        pin = int(os.getenv("LED_PIN", "17"))
        active_high = _to_bool(os.getenv("LED_ACTIVE_HIGH", "true"))
        _LEDS[_DEFAULT_NAME] = LED(pin, active_high=active_high)
        print(f"[LED] init ok (single): pin={pin}, active_high={active_high}")


def light_on(name: Optional[str] = None):
    try:
        _pick(name).on()
    except Exception as e:
        print(f"[LED] on {name or ''} → {e}")


def light_off(name: Optional[str] = None):
    try:
        _pick(name).off()
    except Exception as e:
        print(f"[LED] off {name or ''} → {e}")


def light_toggle(name: Optional[str] = None):
    try:
        _pick(name).toggle()
    except Exception as e:
        print(f"[LED] toggle {name or ''} → {e}")


# （可選）提供列出目前可用 LED 名稱的輔助函式
def list_leds() -> Dict[str, str]:
    """
    回傳 {name: '<repr>'}，可用來除錯。
    """
    return {k: repr(v) for k, v in _LEDS.items()}
