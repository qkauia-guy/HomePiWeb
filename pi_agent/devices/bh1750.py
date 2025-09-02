# -*- coding: utf-8 -*-
"""
BH1750 照度感測器驅動（穩定 one-shot 版）
- 每次 read_lux() 都送一次量測指令（避免連續模式卡死只回 0）
- 初始化會設定 MTreg（預設 69），可依需求調整靈敏度
- 發生 I2C 例外時會自我恢復（POWER_ON/RESET/重設 MTreg）
"""
from __future__ import annotations
import time
from typing import Optional

try:
    from smbus2 import SMBus  # type: ignore
except Exception as e:  # pragma: no cover
    SMBus = None  # type: ignore
    _IMPORT_ERR = e
else:
    _IMPORT_ERR = None

# 指令集
_POWER_DOWN = 0x00
_POWER_ON = 0x01
_RESET = 0x07

# 連續模式（目前不使用，但保留）
_CONT_H_RES = 0x10  # 1 lx/bit
_CONT_H_RES2 = 0x11  # 0.5 lx/bit
_CONT_L_RES = 0x13  # 4 lx/bit

# 一次量測模式（本驅動預設使用）
_ONE_H_RES = 0x20  # 1 lx/bit
_ONE_H_RES2 = 0x21  # 0.5 lx/bit
_ONE_L_RES = 0x23  # 4 lx/bit

# 設定量測時間 (MTreg)
_SET_MTREG_HI = 0x40
_SET_MTREG_LO = 0x60
_DEFAULT_MTREG = 69  # 典型值（越大越靈敏，31~254）


class BH1750:
    def __init__(
        self,
        bus: int = 1,
        addr: int = 0x23,
        mtreg: int = _DEFAULT_MTREG,
        hres2: bool = False,
    ):
        """
        :param bus:   I2C bus 編號（樹莓派通常是 1）
        :param addr:  I2C 位址（常見 0x23 或 0x5C）
        :param mtreg: 測光時間 (31~254)，預設 69
        :param hres2: True=0.5 lx/bit，False=1 lx/bit
        """
        if SMBus is None:
            raise RuntimeError(f"smbus2 未安裝：{_IMPORT_ERR}")

        self.bus_num = int(bus)
        self.addr = int(addr)
        self.mtreg = max(31, min(254, int(mtreg)))
        self.hres2 = bool(hres2)
        self.bus: Optional[SMBus] = None

        self._open()
        self._init_sensor()

    # ---- 基礎 ----
    def _open(self):
        try:
            self.bus = SMBus(self.bus_num)
        except Exception as e:
            raise RuntimeError(f"[BH1750] 開啟 I2C 失敗：{e}")

    def close(self):
        try:
            if self.bus:
                self.bus.close()
        finally:
            self.bus = None

    # ---- 設備初始化 / 恢復 ----
    def _write(self, byte: int):
        assert self.bus is not None
        self.bus.write_byte(self.addr, byte)

    def _set_mtreg(self, mt: int):
        mt = max(31, min(254, int(mt)))
        self._write(_SET_MTREG_HI | (mt >> 5))
        self._write(_SET_MTREG_LO | (mt & 0x1F))
        self.mtreg = mt

    def _init_sensor(self):
        assert self.bus is not None
        # 上電 + 重置 + 設定 MTreg
        self._write(_POWER_ON)
        time.sleep(0.01)
        self._write(_RESET)
        time.sleep(0.01)
        self._set_mtreg(self.mtreg)
        # 不進連續模式；改在 read_lux 做 one-shot
        # 預熱等待（依 MTreg 比例）
        time.sleep(0.02)
        print(
            f"[BH1750] init ok (bus={self.bus_num}, addr=0x{self.addr:02x}, mtreg={self.mtreg})"
        )

    def _recover(self):
        """發生例外時的自我恢復。"""
        try:
            if self.bus is None:
                self._open()
            self._init_sensor()
        except Exception:
            # 讓上層回傳 None，下一輪再試
            pass

    # ---- 讀值（one-shot）----
    def read_lux(self) -> Optional[float]:
        """
        發一次「一次量測」指令，等待整合時間後讀兩個 bytes。
        回傳 lux（float）；如發生 I2C 例外則回 None。
        """
        if self.bus is None:
            return None
        try:
            # 送一次量測（高解析度）
            cmd = _ONE_H_RES2 if self.hres2 else _ONE_H_RES
            self._write(_POWER_ON)
            # 重新設定 MTreg（保險，避免外部把暫存器改掉）
            self._set_mtreg(self.mtreg)
            self._write(cmd)

            # 等待整合時間（典型 ~180ms；依 MTreg 線性調整）
            integ = 0.180 * (self.mtreg / _DEFAULT_MTREG)
            time.sleep(integ)

            # 讀兩個位元組
            data = self.bus.read_i2c_block_data(self.addr, 0x00, 2)
            if not data or len(data) < 2:
                return None

            raw = (data[0] << 8) | data[1]
            # 依據資料手冊：lux ≈ raw / 1.2，MTreg 比例修正
            lux = (raw / 1.2) * (_DEFAULT_MTREG / float(self.mtreg))
            return float(lux)

        except Exception as e:
            print(f"[BH1750] read error: {e}，嘗試恢復")
            self._recover()
            return None
