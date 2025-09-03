# -*- coding: utf-8 -*-
"""
LED 控制模組（devices/led.py）
- 優先讀取 YAML 設定（HOMEPI_CONFIG 或 ./config/homepi.yml）
- YAML 可定義多顆 LED；若沒有 YAML，則回退到環境變數：
    LED_PIN（預設 17）、LED_ACTIVE_HIGH（預設 true）
- 舊介面相容：light_on()/light_off()/light_toggle() 不帶參數會操作第一顆
- 非樹莓派或缺少 gpiozero 時，進入 no-op（只印訊息），但會維護「陰影狀態」
- 新增：
    - is_on(name) 取得目前燈狀態（gpiozero 為準，否則用陰影狀態）
    - 於 setup / on / off / toggle 自動同步陰影狀態
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

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

# ★ 陰影狀態（在無 gpiozero 或例外時也能回報狀態）
_STATE_ON: Dict[str, bool] = {}


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
    cfg_path = os.environ.get("HOMEPI_CONFIG")
    cand = None
    if cfg_path:
        cand = Path(cfg_path)
    else:
        # devices/ 的上一層就是專案根
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


def _pick_name(name: Optional[str]) -> str:
    """
    決定要操作的 LED 名稱：
      - 有傳且存在就用傳入
      - 否則若有已初始化的第一顆
      - 否則回退到預設名稱（no-op 情境也需要有個 key）
    """
    if name and name in _LEDS:
        return name
    if _LEDS:
        return next(iter(_LEDS.keys()))
    return name or _DEFAULT_NAME


def _get_led_and_name(name: Optional[str]) -> Tuple[Optional["LED"], str]:
    eff = _pick_name(name)
    return _LEDS.get(eff), eff


def _shadow_set(eff_name: str, on: bool):
    """同步陰影狀態（以『實際使用的名稱』為 key）。"""
    _STATE_ON[eff_name] = bool(on)


# === 對外 API ===
def setup_led(cfg: Optional[dict] = None):
    """
    建立多顆 LED：
      - 若 cfg 省略：自動嘗試讀取 YAML；若無 YAML → 回退環境變數（單顆）
      - 若有 YAML：devices: [ {name, kind: led, pin, active_high}, ... ]
      - 若沒有 gpiozero：no-op（只印出動作），但仍初始化陰影狀態，之後 is_on() 可用
    """
    global _LEDS

    # 先清空（避免重複呼叫造成殘留）
    for led in _LEDS.values():
        try:
            led.close()
        except Exception:
            pass
    _LEDS.clear()
    _STATE_ON.clear()

    # 讀設定
    cfg = cfg or _load_yaml_config()
    gpio_factory = cfg.get("gpio_factory")
    if gpio_factory and "GPIOZERO_PIN_FACTORY" not in os.environ:
        os.environ["GPIOZERO_PIN_FACTORY"] = str(gpio_factory)

    devices = [d for d in (cfg.get("devices") or []) if d.get("kind") == "led"]

    # 如果沒有 gpiozero，就 no-op，但仍建立陰影名稱
    if LED is None:
        print("[WARN] gpiozero 不可用：", _GPIO_ERR, "（LED 進入 no-op 模式）")
        if devices:
            for i, d in enumerate(devices):
                name = str(d.get("name") or (i == 0 and _DEFAULT_NAME) or f"led_{i+1}")
                _STATE_ON[name] = False  # 預設皆為關
            names = list(_STATE_ON.keys())
            print(f"[LED] 已從 YAML 解析到 LED（no-op）：{names}")
        else:
            # YAML 沒有 → 嘗試環境變數建立單顆陰影
            name = _DEFAULT_NAME
            _STATE_ON[name] = False
            pin = int(os.getenv("LED_PIN", "17"))
            active_high = _to_bool(os.getenv("LED_ACTIVE_HIGH", "true"))
            print(
                f"[LED] 使用環境變數（單顆，no-op）：name={name}, pin={pin}, active_high={active_high}"
            )
        return

    # 有 gpiozero：真的建立 LED
    if devices:
        for i, d in enumerate(devices):
            name = str(d.get("name") or (i == 0 and _DEFAULT_NAME) or f"led_{i+1}")
            pin = int(d["pin"])
            active_high = _to_bool(d.get("active_high"), True)
            obj = LED(pin, active_high=active_high)
            _LEDS[name] = obj
            # 初始化陰影狀態
            try:
                _STATE_ON[name] = bool(getattr(obj, "is_lit", False))
            except Exception:
                _STATE_ON[name] = False
            print(f"[LED] init ok: {name} (pin={pin}, active_high={active_high})")
    else:
        # YAML 沒有 → fallback 環境變數（單顆）
        name = _DEFAULT_NAME
        pin = int(os.getenv("LED_PIN", "17"))
        active_high = _to_bool(os.getenv("LED_ACTIVE_HIGH", "true"))
        obj = LED(pin, active_high=active_high)
        _LEDS[name] = obj
        try:
            _STATE_ON[name] = bool(getattr(obj, "is_lit", False))
        except Exception:
            _STATE_ON[name] = False
        print(
            f"[LED] init ok (single): name={name}, pin={pin}, active_high={active_high}"
        )


def light_on(name: Optional[str] = None):
    led, eff = _get_led_and_name(name)
    try:
        if led is not None:
            led.on()
    except Exception as e:
        print(f"[LED] on {eff} → {e}")
    finally:
        _shadow_set(eff, True)


def light_off(name: Optional[str] = None):
    led, eff = _get_led_and_name(name)
    try:
        if led is not None:
            led.off()
    except Exception as e:
        print(f"[LED] off {eff} → {e}")
    finally:
        _shadow_set(eff, False)


def light_toggle(name: Optional[str] = None):
    led, eff = _get_led_and_name(name)
    try:
        if led is not None:
            led.toggle()
            try:
                _shadow_set(eff, bool(getattr(led, "is_lit", False)))
            except Exception:
                _shadow_set(eff, not _STATE_ON.get(eff, False))
        else:
            # no-op：只翻轉陰影
            _shadow_set(eff, not _STATE_ON.get(eff, False))
    except Exception as e:
        print(f"[LED] toggle {eff} → {e}")
        _shadow_set(eff, not _STATE_ON.get(eff, False))


def is_on(name: Optional[str] = None) -> bool:
    """
    回傳指定名稱（或預設/第一顆）LED 是否點亮。
    gpiozero 可用 → 讀硬體；否則回傳陰影狀態。
    """
    eff = _pick_name(name)
    led = _LEDS.get(eff)
    if led is not None:
        try:
            return bool(getattr(led, "is_lit", False))
        except Exception:
            pass
    return bool(_STATE_ON.get(eff, False))


# （可選）提供列出目前可用 LED 名稱與 repr 的輔助函式
def list_leds() -> Dict[str, str]:
    """
    回傳 {name: '<repr>'}，可用來除錯。
    """
    return {k: repr(v) for k, v in _LEDS.items()}
