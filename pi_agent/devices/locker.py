# -*- coding: utf-8 -*-
from __future__ import annotations  # ← 必須放最前面！

"""
電子鎖控制模組（devices/locker.py）
- 改用 gpiozero（AngularServo / LED），相容 GPIOZERO_PIN_FACTORY=lgpio
- 保留原公開函式：setup_locker / lock / unlock / toggle / is_locked /
  get_state / list_lockers / close_all / set_state_push
- YAML 結構不變：devices[kind=locker].config.{button_pin,servo_pin,led_green,led_red,auto_lock_delay}
"""

import os
import time
import threading
from typing import Optional, Dict, Any, Callable

from gpiozero import Device
from gpiozero.pins.lgpio import LGPIOFactory

Device.pin_factory = LGPIOFactory()


# 儘早偵測 gpiozero；失敗則進入 no-op（仍解析 YAML、保留名稱清單）
try:
    from gpiozero import AngularServo, LED, Button  # type: ignore
except Exception as _e:
    AngularServo = None  # type: ignore
    LED = None  # type: ignore
    Button = None  # type: ignore
    _GZ_ERR = _e
else:
    _GZ_ERR = None

# 內部狀態
_lockers: Dict[str, "LockerDevice | None"] = {}
_DEFAULT_NAME = "locker_1"  # 不帶參數時操作的預設名稱

# 狀態回推 callback（由外部註冊；例如 http_agent 設定為 push ping）
_push_state_cb: Optional[Callable[[], None]] = None


class LockerDevice:
    """單一電子鎖裝置（gpiozero 版本）"""

    def __init__(
        self,
        name: str,
        button_pin: int = 27,
        servo_pin: int = 18,
        led_green: int = 23,
        led_red: int = 22,
        auto_lock_delay: int = 0,
        # 需要可以微調脈寬時可在 YAML config 內加上（選用）
        servo_min_us: int = 500,
        servo_max_us: int = 2500,
        # 是否在啟動時立即把伺服馬達轉到上鎖角度
        lock_on_boot: bool = True,
        # 動作後是否自動 detach PWM，避免持續抖動（軟體 PWM 常見）
        detach_after_move: bool = True,
        # 簡化模式：僅控制伺服（忽略 LED / Button / 自動上鎖）
        simple_mode: bool = True,
    ):
        self.name = name
        self.button_pin = int(button_pin)
        self.servo_pin = int(servo_pin)
        self.led_green_pin = int(led_green)
        self.led_red_pin = int(led_red)
        self.auto_lock_delay = int(auto_lock_delay)
        self._servo_min_us = int(servo_min_us)
        self._servo_max_us = int(servo_max_us)
        self._lock_on_boot = bool(lock_on_boot)
        self._detach_after_move = bool(detach_after_move)
        self._simple_mode = bool(simple_mode)

        self.locked = True  # 初始狀態為上鎖
        self._lock = threading.Lock()
        self.auto_lock_thread: Optional[threading.Thread] = None

        # gpiozero 裝置（可能為 None：若 gpiozero 不可用）
        self.servo: Optional[AngularServo] = None
        self._led_green: Optional[LED] = None
        self._led_red: Optional[LED] = None
        self._button: Optional[Button] = None

        # 初始化硬體
        self._setup_gz()

    # ---- 硬體初始化（gpiozero） ----
    def _setup_gz(self):
        if AngularServo is None or LED is None:
            print(f"[Locker] gpiozero 不可用：{_GZ_ERR}（{self.name} 進入 no-op）")
            return
        try:
            # 多數 SG90/微伺服：0.5ms~2.5ms，角度 0~180
            self.servo = AngularServo(
                self.servo_pin,
                min_angle=0,
                max_angle=180,
                min_pulse_width=self._servo_min_us / 1_000_000.0,
                max_pulse_width=self._servo_max_us / 1_000_000.0,
            )
            if not self._simple_mode:
                self._led_green = LED(self.led_green_pin)
                self._led_red = LED(self.led_red_pin)

            # ★ 開機行為：是否立即轉到既定角度
            if self._lock_on_boot:
                # 根據 locked 狀態設定角度：True=上鎖(90度), False=開鎖(0度)
                initial_angle = 90 if self.locked else 0
                self.servo.angle = initial_angle
                print(f"[Locker] {self.name} 初始化設定角度→{initial_angle}°")
            else:
                # 不主動轉動伺服（避免開機自轉）；保持目前角度
                try:
                    self.servo.detach()
                except Exception:
                    pass
                print(f"[Locker] {self.name} 啟動時不移動伺服（lock_on_boot=false）")

            # 設定對應的 LED 狀態（簡化模式略過）
            if not self._simple_mode:
                self._led_set(green_on=not self.locked, red_on=self.locked)

            # 選配：按鈕（上拉/下拉交由硬體/外部電路決定）
            if (not self._simple_mode) and Button is not None and self.button_pin >= 0:
                try:
                    self._button = Button(self.button_pin, bounce_time=0.05)
                    # 預設：按一下切換
                    self._button.when_pressed = self.toggle
                except Exception as e:
                    print(f"[Locker] {self.name} Button 初始化失敗：{e}")
                    self._button = None

            print(f"[Locker] {self.name} gpiozero 初始化完成")
        except Exception as e:
            print(f"[Locker] {self.name} 初始化失敗：{e}")
            self.servo = None
            self._led_green = None
            self._led_red = None
            self._button = None

    # ---- 低階操作 ----
    def _set_angle(self, angle: int):
        if not self.servo:
            print(f"[Locker] {self.name} (no-op) 設定角度→{angle}")
            return
        try:
            print(f"[DEBUG] {self.name} 開始設定角度→{angle}")
            # 確保 servo 被重新啟用
            if hasattr(self.servo, "attach"):
                try:
                    print(f"[DEBUG] {self.name} 嘗試 attach servo")
                    self.servo.attach()
                    print(f"[DEBUG] {self.name} servo attach 成功")
                except Exception as e:
                    print(f"[DEBUG] {self.name} servo attach 失敗: {e}")
                    pass
            a = max(0, min(180, int(angle)))
            print(f"[DEBUG] {self.name} 設定 servo.angle = {a}")
            self.servo.angle = a
            print(f"[DEBUG] {self.name} servo.angle 設定完成，等待 0.6 秒")
            time.sleep(0.6)
            print(f"[DEBUG] {self.name} 等待完成")
            if self._detach_after_move:
                try:
                    print(f"[DEBUG] {self.name} 嘗試 detach servo")
                    self.servo.detach()
                    print(f"[DEBUG] {self.name} servo detach 成功")
                except Exception as e:
                    print(f"[DEBUG] {self.name} servo detach 失敗: {e}")
                    pass
            print(f"[DEBUG] {self.name} 角度設定完成")
        except Exception as e:
            print(f"[Locker] {self.name} 設定角度失敗：{e}")

    def _led_set(self, green_on: bool, red_on: bool):
        try:
            if self._led_green:
                (self._led_green.on() if green_on else self._led_green.off())
            if self._led_red:
                (self._led_red.on() if red_on else self._led_red.off())
        except Exception as e:
            print(f"[Locker] {self.name} LED 控制失敗：{e}")

    def _push_state(self):
        try:
            if _push_state_cb:
                # 使用 threading.Timer 來避免死鎖
                import threading
                timer = threading.Timer(0.1, _push_state_cb)
                timer.start()
        except Exception as e:
            print(f"[Locker] {self.name} 狀態回推失敗：{e}")

    # ---- 邏輯 ----
    def _lock_internal(self):
        print(f"[Locker] {self.name} 上鎖")
        self._set_angle(90)
        if not self._simple_mode:
            self._led_set(green_on=False, red_on=True)
        self.locked = True

    def _unlock_internal(self):
        print(f"[Locker] {self.name} 開鎖")
        self._set_angle(0)
        if not self._simple_mode:
            self._led_set(green_on=True, red_on=False)
        self.locked = False

    def _auto_lock_worker(self):
        # 背景延遲自動上鎖
        time.sleep(max(0, self.auto_lock_delay))
        with self._lock:
            if not self.locked:
                self._lock_internal()
                print(f"[Locker] {self.name} 自動上鎖完成")
                self._push_state()
        self.auto_lock_thread = None

    # ---- 公開動作 ----
    def lock(self):
        with self._lock:
            self._lock_internal()
            # 取消自動上鎖
            self.auto_lock_thread = None
            self._push_state()

    def unlock(self):
        with self._lock:
            self._unlock_internal()
            # 簡化模式：不啟動自動上鎖
            if (
                (not self._simple_mode)
                and self.auto_lock_thread is None
                and self.auto_lock_delay > 0
            ):
                t = threading.Thread(target=self._auto_lock_worker, daemon=True)
                self.auto_lock_thread = t
                t.start()
                print(f"[Locker] {self.name} {self.auto_lock_delay}秒後自動上鎖…")
            self._push_state()

    def toggle(self):
        if self.is_locked():
            self.unlock()
        else:
            self.lock()

    # ---- 狀態 ----
    def is_locked(self) -> bool:
        with self._lock:
            return bool(self.locked)

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "locked": bool(self.locked),
                "auto_lock_running": self.auto_lock_thread is not None,
                "name": self.name,
            }

    # ---- 收尾 ----
    def close(self):
        with self._lock:
            self.auto_lock_thread = None
            # 回到安全狀態（可選）：上鎖+關綠燈開紅燈
            try:
                self._lock_internal()
            except Exception:
                pass
            # 釋放資源
            try:
                if self.servo:
                    # 停止 PWM 輸出，避免開機時自轉
                    self.servo.detach()
            except Exception:
                pass
            try:
                if self._led_green:
                    self._led_green.off()
                if self._led_red:
                    self._led_red.on()
            except Exception:
                pass
        print(f"[Locker] {self.name} 已關閉")


# ===== 模組級 utilities =====


def _to_int(v, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return int(default)


def _load_yaml_config() -> dict:
    """載入 YAML 設定（homepi.yml）"""
    cfg_path = os.environ.get("HOMEPI_CONFIG")
    if cfg_path:
        from pathlib import Path

        cand = Path(cfg_path)
    else:
        from pathlib import Path

        cand = Path(__file__).resolve().parent.parent / "config" / "homepi.yml"

    try:
        import yaml  # type: ignore
    except Exception:
        return {}

    try:
        if cand and cand.is_file():
            with open(cand, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"[Locker] YAML 讀取失敗：{e}")
    return {}


def setup_locker(cfg: Optional[dict] = None):
    """初始化電子鎖（可重入）"""
    global _lockers

    # 先清理現有裝置
    for lk in list(_lockers.values()):
        if lk:
            lk.close()
    _lockers.clear()

    cfg = cfg or _load_yaml_config()
    devices = [
        d
        for d in (cfg.get("devices") or [])
        if (d.get("kind") or "").lower() == "locker"
    ]

    if not devices:
        # 沒在 YAML：給一個預設（也讓 no-op 情境能看到名稱）
        name = _DEFAULT_NAME
        if AngularServo is None:
            print(f"[WARN] gpiozero 不可用：{_GZ_ERR}（電子鎖進入 no-op 模式）")
            _lockers[name] = None
            return
        _lockers[name] = LockerDevice(name=name)
        print(f"[Locker] 使用預設設定初始化：{name}")
        return

    # 依 YAML 建立
    for i, d in enumerate(devices):
        name = str(d.get("name") or (i == 0 and _DEFAULT_NAME) or f"locker_{i+1}")
        conf = d.get("config") or {}

        if AngularServo is None:
            print(f"[WARN] gpiozero 不可用：{_GZ_ERR}（{name} no-op）")
            _lockers[name] = None
            continue

        locker = LockerDevice(
            name=name,
            button_pin=_to_int(conf.get("button_pin", -1), -1),
            servo_pin=_to_int(conf.get("servo_pin", 18), 18),
            led_green=_to_int(conf.get("led_green", -1), -1),
            led_red=_to_int(conf.get("led_red", -1), -1),
            auto_lock_delay=_to_int(conf.get("auto_lock_delay", 0), 0),
            servo_min_us=_to_int(conf.get("servo_min_us", 500), 500),
            servo_max_us=_to_int(conf.get("servo_max_us", 2500), 2500),
            lock_on_boot=bool(conf.get("lock_on_boot", True)),
        )
        _lockers[name] = locker
        print(f"[Locker] 初始化完成：{name}")


def _pick_name(name: Optional[str]) -> str:
    if name and name in _lockers:
        return name
    if _lockers:
        return next(iter(_lockers.keys()))
    return name or _DEFAULT_NAME


def _get_locker_and_name(name: Optional[str]) -> tuple[Optional[LockerDevice], str]:
    eff = _pick_name(name)
    return _lockers.get(eff), eff


def set_state_push(cb: Optional[Callable[[], None]]) -> None:
    """由 http_agent 註冊：狀態變更即時回推"""
    global _push_state_cb
    _push_state_cb = cb
    print("[DEBUG] locker.set_state_push called ->", cb)


def lock(name: Optional[str] = None):
    lk, eff = _get_locker_and_name(name)
    if lk:
        lk.lock()
    else:
        print(f"[Locker] {eff} 不存在或未初始化（no-op）")


def unlock(name: Optional[str] = None):
    lk, eff = _get_locker_and_name(name)
    if lk:
        lk.unlock()
    else:
        print(f"[Locker] {eff} 不存在或未初始化（no-op）")


def toggle(name: Optional[str] = None):
    lk, eff = _get_locker_and_name(name)
    if lk:
        lk.toggle()
    else:
        print(f"[Locker] {eff} 不存在或未初始化（no-op）")


def is_locked(name: Optional[str] = None) -> bool:
    lk, _ = _get_locker_and_name(name)
    return bool(lk.is_locked()) if lk else False


def get_state(name: Optional[str] = None) -> Dict[str, Any]:
    lk, eff = _get_locker_and_name(name)
    if lk:
        return lk.get_state()
    return {"locked": False, "auto_lock_running": False, "name": eff}


def list_lockers() -> Dict[str, str]:
    return {
        k: (f"<LockerDevice: {k}>" if v else "<LockerDevice: no-op>")
        for k, v in _lockers.items()
    }


def close_all():
    for lk in list(_lockers.values()):
        if lk:
            lk.close()
    _lockers.clear()
