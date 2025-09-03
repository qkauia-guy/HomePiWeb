# -*- coding: utf-8 -*-
"""
utils/auto_light.py  (optimized)
- 背景執行緒：讀 BH1750 → 依門檻 + 去抖動控制 LED
- 立即回推狀態：燈真正切換時呼叫外部 callback（通常是 http.ping(extra={"state": ...})）
- 可查詢狀態：get_state()
"""

from __future__ import annotations
import threading
import time
from typing import Optional, Dict, Any, Callable

# 你的模組
from devices.bh1750 import BH1750
from devices import led as led_mod

# ===== 內部狀態 =====
_running_lock = threading.Lock()
_running_flag = False
_stop_evt: Optional[threading.Event] = None
_thread: Optional[threading.Thread] = None

_last_lux: Optional[float] = None
_led_name: Optional[str] = None
_is_on: bool = False
_last_change_ts: Optional[float] = None

# 外部註冊：當 state 改變時要做什麼（例如呼叫 http.ping(...)）
_push_state_cb: Optional[Callable[[], None]] = None


# ===== 小工具 =====
def _to_bool(val, default: bool = True) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")


def _to_int(v, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


def _to_float(v, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)


def _resolve_sensor_cfg(
    cfg: Dict[str, Any], sensor_name: str
) -> Optional[Dict[str, int]]:
    """
    從 YAML cfg['devices'] 找到 name= sensor_name 的 bus/addr；若找不到，嘗試由名稱 'bh1750-<bus>-<addr>'
    """
    devs = (cfg or {}).get("devices") or []
    for d in devs:
        if d.get("name") == sensor_name:
            bus = _to_int((d.get("config") or {}).get("bus", d.get("bus", 1)), 1)
            addr = _to_int(
                (d.get("config") or {}).get("addr", d.get("addr", 0x23)), 0x23
            )
            return {"bus": bus, "addr": addr}

    # name 形如 bh1750-1-23
    try:
        if sensor_name.lower().startswith("bh1750-"):
            _, b, a = sensor_name.split("-", 2)
            bus = _to_int(b, 1)
            # addr 可能是 0x23 或 35 或 '23'
            a_str = str(a).lower().replace("0x", "")
            addr = (
                int(a_str, 16)
                if all(c in "0123456789abcdef" for c in a_str)
                else _to_int(a, 0x23)
            )
            return {"bus": bus, "addr": addr}
    except Exception:
        pass
    return None


def set_state_push(cb: Optional[Callable[[], None]]) -> None:
    """由外部（http_agent）設定：當燈狀態改變時要做什麼（例如 HTTP ping 回報 state）"""
    global _push_state_cb
    _push_state_cb = cb


def _push_state_now():
    """安全呼叫 callback（不要讓例外中斷主流程）"""
    try:
        if _push_state_cb:
            _push_state_cb()
    except Exception as e:
        print(f"[auto_light] push state err: {e}")


def _set_last_lux(v: Optional[float]) -> None:
    global _last_lux
    _last_lux = v


# ===== 對外查詢 =====
def get_last_lux() -> Optional[float]:
    return _last_lux


def is_running() -> bool:
    return bool(_running_flag)


def get_state() -> dict:
    """回傳目前狀態：給 http_agent._build_state_blob 使用"""
    try:
        led_on = led_mod.is_on(_led_name) if _led_name else False
    except Exception:
        led_on = False
    return {
        "running": bool(_running_flag),
        "last_lux": _last_lux,
        "led": _led_name,
        "led_is_on": bool(led_on),
        "last_change_ts": _last_change_ts,
    }


# ===== 主工作執行緒 =====
def _worker(cfg: Dict[str, Any]):
    global _stop_evt, _running_flag, _is_on, _last_change_ts, _led_name

    # ---- 讀設定（含邊界保護）----
    auto = (cfg or {}).get("auto_light", {}) or {}
    if not _to_bool(auto.get("enabled"), False):
        print("[auto_light] 未啟用，結束。")
        return

    sensor_name = auto.get("sensor") or "bh1750-1-23"
    _led_name = auto.get("led") or None
    on_below = max(0.0, _to_float(auto.get("on_below", 80.0), 80.0))
    off_above = max(
        on_below + 1e-6, _to_float(auto.get("off_above", 120.0), 120.0)
    )  # 確保回滯
    every_ms = max(200, _to_int(auto.get("sample_every_ms", 1000), 1000))  # 下限 200ms
    need_n = max(1, _to_int(auto.get("require_n_samples", 3), 3))
    debug = _to_bool(auto.get("debug"), False)
    log_every = max(0, _to_int(auto.get("log_every", 0), 0))

    # 解析感測器 bus/addr
    sconf = _resolve_sensor_cfg(cfg, sensor_name)
    if not sconf:
        print(f"[auto_light] 找不到感測器設定：{sensor_name}")
        return
    bus, addr = sconf["bus"], sconf["addr"]

    # 確保 LED 初始化
    try:
        if not led_mod.list_leds():
            led_mod.setup_led(cfg)
    except Exception:
        led_mod.setup_led(cfg)

    # 建立感測器
    sensor: Optional[BH1750] = None
    try:
        sensor = BH1750(bus=bus, addr=addr)
        print(
            f"[auto_light] 啟動，sensor={sensor_name} -> bus={bus} addr=0x{addr:02x}, "
            f"led={_led_name or '(default)'} on_below={on_below} off_above={off_above}, "
            f"every={every_ms}ms need_n={need_n}"
        )
    except Exception as e:
        print(f"[auto_light] 建立 BH1750 失敗：{e}")
        return

    _stop_evt = threading.Event()
    below_cnt = 0
    above_cnt = 0
    loop = 0

    # 進入執行狀態
    try:
        # warm-up：先讀一次，立刻回推一次初始狀態
        lux0 = None
        try:
            lux0 = sensor.read_lux()
            _set_last_lux(lux0)
        except Exception as e:
            print(f"[auto_light] warm-up 讀取失敗：{e}")
        _push_state_now()  # 讓 UI 先拿到初始 lux / running

        while not _stop_evt.is_set():
            try:
                loop += 1
                lux = sensor.read_lux()
                _set_last_lux(lux)

                if lux is None:
                    if debug:
                        print("[auto_light] lux=None（讀取失敗）")
                    if _stop_evt.wait(every_ms / 1000.0):
                        break
                    continue

                if log_every and (loop % log_every == 0):
                    print(
                        f"[auto_light] lux={lux:.2f} "
                        f"(is_on={_is_on}, below_cnt={below_cnt}, above_cnt={above_cnt})"
                    )

                # 去抖 + 回滯
                if lux < on_below:
                    below_cnt += 1
                    above_cnt = 0
                elif lux > off_above:
                    above_cnt += 1
                    below_cnt = 0
                else:
                    below_cnt = 0
                    above_cnt = 0

                # 開燈
                if (not _is_on) and below_cnt >= need_n:
                    led_mod.light_on(_led_name)
                    _is_on = True
                    below_cnt = 0
                    _last_change_ts = time.time()
                    print(f"[auto_light] lux={lux:.2f} → 開燈")
                    _push_state_now()  # ★ 立即回推

                # 關燈
                elif _is_on and above_cnt >= need_n:
                    led_mod.light_off(_led_name)
                    _is_on = False
                    above_cnt = 0
                    _last_change_ts = time.time()
                    print(f"[auto_light] lux={lux:.2f} → 關燈")
                    _push_state_now()  # ★ 立即回推

                if _stop_evt.wait(every_ms / 1000.0):
                    break

            except Exception as e:
                # 單次例外不終止執行緒
                print(f"[auto_light] 迴圈例外：{e}")
                if _stop_evt.wait(1.0):
                    break
                continue

    finally:
        try:
            if sensor:
                sensor.close()
        except Exception:
            pass
        print("[auto_light] 已停止。")


# ===== 對外 API =====
def start_auto_light(cfg: Dict[str, Any]) -> None:
    """啟動（若已在跑就直接回報『已在執行中』）"""
    global _running_flag, _thread
    with _running_lock:
        if _running_flag:
            print("[auto_light] 已在執行中。")
            return
        _running_flag = True
        # 重置狀態
        _set_last_lux(None)
        # 不去猜硬體狀態，由 led_mod.is_on 真實回
    t = threading.Thread(target=_worker, args=(cfg,), daemon=True)
    _thread = t
    t.start()


def stop_auto_light(wait: bool = False, timeout: Optional[float] = 3.0) -> None:
    """停止；wait=True 時同步等待（最多 timeout 秒）"""
    global _running_flag, _stop_evt, _thread
    with _running_lock:
        if not _running_flag:
            return
        _running_flag = False
        if _stop_evt:
            _stop_evt.set()

    if wait and _thread is not None:
        try:
            _thread.join(timeout=timeout)
        except Exception:
            pass
        finally:
            _thread = None
