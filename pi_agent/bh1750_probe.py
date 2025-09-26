# bh1750_probe.py
import time
from smbus2 import SMBus

# 一次高解析度模式（1.0 lx/bit，典型180ms）
ONE_TIME_H_RES = 0x20
POWER_ON  = 0x01
RESET     = 0x07

def read_once(bus, addr, mtreg=69):
    try:
        # Power on + reset
        bus.write_byte(addr, POWER_ON)
        time.sleep(0.01)
        bus.write_byte(addr, RESET)
        time.sleep(0.01)
        # 設定 MTreg（可選，預設69），範圍 31~254
        mtreg = max(31, min(254, int(mtreg)))
        bus.write_byte(addr, 0x40 | (mtreg >> 5))    # 高 3 bits
        bus.write_byte(addr, 0x60 | (mtreg & 0x1F))  # 低 5 bits
        # 啟動一次量測
        bus.write_byte(addr, ONE_TIME_H_RES)
        # 等待整合時間（典型120~180ms；依 MTreg 線性調整）
        time.sleep(0.180 * (mtreg / 69.0))
        raw = bus.read_i2c_block_data(addr, 0x00, 2)
        val = (raw[0] << 8) | raw[1]
        # 1 lx/bit，數據手冊係數 1.2，MTreg 比例修正
        lux = (val / 1.2) * (69.0 / mtreg)
        return raw, val, lux
    except Exception as e:
        return None, None, None

def probe(addr):
    with SMBus(1) as bus:
        print(f"=== Probe BH1750 @ 0x{addr:02x} ===")
        for i in range(20):
            raw, val, lux = read_once(bus, addr, mtreg=69)
            if raw is None:
                print("read fail")
            else:
                print(f"raw={raw} val={val} lux={lux:.2f}")
            time.sleep(0.5)

if __name__ == "__main__":
    # 兩個常見位址都測
    for a in (0x23, 0x5C):
        probe(a)
        print()
