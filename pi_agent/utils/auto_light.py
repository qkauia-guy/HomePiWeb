# -*- coding: utf-8 -*-
"""
自動開關燈背景執行緒（utils/auto_light.py）
- 從 YAML 讀取 auto_light 設定
- 定期讀 BH1750 照度，套用門檻 + 回滯 + 多樣本去抖動
- 透過 devices/led.py 控制燈
- 提供狀態查詢（is_running / get_last_lux）
"""
from __future__ import annotations
import threading
import time
from typing import Optional, Dict, Any

# 你的模組
from devices.bh1750 import BH1750
from devices import led as led_mod

# === 執行緒與狀態 ===
_running_lock = threading.Lock()
_running_flag = False
_stop_evt: Optional[threading.Event] = None
_thread: Optional[threading.Thread] = None
_last_lux: Optional[float] = None  # 最近一次量到的 lux


# === 小工具 ===
def _to_bool(val, default=True) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes", "y", "on")


def _set_last_lux(v: Optional[float]) -> None:
    global _last_lux
    _last_lux = v


def get_last_lux() -> Optional[float]:
    """回傳最近一次量到的 lux（可能為 None）。"""
    return _last_lux


def is_running() -> bool:
    """是否有自動感光執行緒在跑。"""
    return bool(_running_flag)


def _resolve_sensor_cfg(
    cfg: Dict[str, Any], sensor_name: str
) -> Optional[Dict[str, int]]:
    """從 YAML 的 devices 找到對應感測器的 bus/addr。"""
    for d in cfg.get("devices") or []:
        if d.get("name") == sensor_name:
            bus = int((d.get("config") or {}).get("bus", d.get("bus", 1)))
            addr = int((d.get("config") or {}).get("addr", d.get("addr", 0x23)))
            return {"bus": bus, "addr": addr}
    return None


# === 主工作執行緒 ===
def _worker(cfg: Dict[str, Any]):
    """
    cfg.auto_light 可用欄位：
      enabled: bool
      sensor: str  ex. "bh1750-1-23"
      led:    str  ex. "led_1"
      on_below: float       低於 → 開燈
      off_above: float      高於 → 關燈
      sample_every_ms: int  取樣間隔（毫秒）
      require_n_samples: int 連續 N 次滿足才觸發
      debug: bool           額外印除錯訊息
      log_every: int        每幾次取樣印一次 lux（0=不印）
    """
    global _stop_evt, _running_flag

    try:
        auto = (cfg or {}).get("auto_light", {}) or {}
        if not _to_bool(auto.get("enabled"), False):
            print("[auto_light] 未啟用，結束。")
            return

        sensor_name = auto.get("sensor") or "bh1750-1-23"
        led_name = auto.get("led") or None  # None → 使用 devices/led.py 預設第一顆
        on_below = float(auto.get("on_below", 80.0))
        off_above = float(auto.get("off_above", 120.0))
        every_ms = int(auto.get("sample_every_ms", 1000))
        need_n = int(auto.get("require_n_samples", 3))
        debug = _to_bool(auto.get("debug"), False)
        log_every = int(auto.get("log_every", 0))

        # 解析感測器 bus/addr
        sconf = _resolve_sensor_cfg(cfg, sensor_name)
        if not sconf:
            print(f"[auto_light] 找不到感測器設定：{sensor_name}")
            return
        bus, addr = sconf["bus"], sconf["addr"]

        # 建立感測器
        sensor = BH1750(bus=bus, addr=addr)

        # 準備 LED（若尚未 setup）
        try:
            if not led_mod.list_leds():
                led_mod.setup_led(cfg)
        except Exception:
            led_mod.setup_led(cfg)

        below_cnt = 0
        above_cnt = 0
        is_on = False  # 程式內部記錄的燈狀態（避免重複 on/off）
        loop = 0

        print(
            f"[auto_light] 啟動，sensor={sensor_name} -> bus={bus} addr=0x{addr:02x}, "
            f"led={led_name or '(default)'} on_below={on_below} off_above={off_above}, "
            f"every={every_ms}ms need_n={need_n}"
        )

        _stop_evt = threading.Event()
        while not _stop_evt.is_set():
            try:
                loop += 1
                lux = sensor.read_lux()
                _set_last_lux(lux)

                if lux is None:
                    if debug:
                        print("[auto_light] lux=None（讀取失敗）")
                    time.sleep(every_ms / 1000.0)
                    continue

                # 每 log_every 次印一次即時狀態
                if log_every and (loop % log_every == 0):
                    print(
                        f"[auto_light] lux={lux:.2f} "
                        f"(is_on={is_on}, below_cnt={below_cnt}, above_cnt={above_cnt})"
                    )

                # 去抖動 + 回滯
                if lux < on_below:
                    below_cnt += 1
                    above_cnt = 0
                elif lux > off_above:
                    above_cnt += 1
                    below_cnt = 0
                else:
                    # 落在回滯區，重置計數
                    below_cnt = 0
                    above_cnt = 0

                # 觸發
                if (not is_on) and below_cnt >= need_n:
                    led_mod.light_on(led_name)
                    is_on = True
                    below_cnt = 0
                    print(f"[auto_light] lux={lux:.2f} → 開燈")
                elif is_on and above_cnt >= need_n:
                    led_mod.light_off(led_name)
                    is_on = False
                    above_cnt = 0
                    print(f"[auto_light] lux={lux:.2f} → 關燈")

                time.sleep(every_ms / 1000.0)

            except Exception as e:
                # 避免單次例外把執行緒殺掉
                print(f"[auto_light] 迴圈例外：{e}")
                time.sleep(1.0)
                continue

        # 結束前釋放硬體
        try:
            sensor.close()
        except Exception:
            pass
        print("[auto_light] 已停止。")

    finally:
        # 無論任何 return 路徑都清除旗標
        with _running_lock:
            _running_flag = False
            _stop_evt = None  # 讓下一次 start 可重新建


# === 對外 API ===
def start_auto_light(cfg: Dict[str, Any]):
    """啟動自動感光執行緒。"""
    global _running_flag, _thread
    with _running_lock:
        if _running_flag:
            print("[auto_light] 已在執行中。")
            return
        _running_flag = True
    t = threading.Thread(target=_worker, args=(cfg,), daemon=True)
    _thread = t
    t.start()


def stop_auto_light(wait: bool = False, timeout: Optional[float] = 3.0):
    """停止自動感光執行緒；wait=True 時會等待最多 timeout 秒。"""
    global _running_flag, _stop_evt, _thread
    with _running_lock:
        if not _running_flag:
            return
        if _stop_evt:
            _stop_evt.set()
        _running_flag = False

    if wait and _thread is not None:
        try:
            _thread.join(timeout=timeout)
        except Exception:
            pass
        finally:
            _thread = None
