def scan_i2c_bus(bus_nums=(1,)):
    found = []
    try:
        from smbus2 import SMBus
    except Exception:
        return found
    for bus in bus_nums:
        try:
            with SMBus(bus) as b:
                for addr in range(0x03, 0x78):
                    try:
                        b.write_quick(addr)
                        found.append({"bus": bus, "addr": addr})
                    except Exception:
                        pass
        except Exception:
            pass
    return found


def detect():
    caps = []
    for dev in scan_i2c_bus():
        if dev["addr"] == 0x40:  # PCA9685（常見 PWM 擴展）
            caps.append(
                {
                    "kind": "pwm_hub",
                    "name": "PCA9685",
                    "slug": f"pca9685-{dev['bus']}-{dev['addr']:02x}",
                    "config": {"bus": dev["bus"], "addr": dev["addr"]},
                    "order": 90,
                    "enabled": True,
                }
            )
        if dev["addr"] in (0x76, 0x77):  # BME280
            caps.append(
                {
                    "kind": "sensor_bme280",
                    "name": "室內環境感測",
                    "slug": f"bme280-{dev['bus']}-{dev['addr']:02x}",
                    "config": {"bus": dev["bus"], "addr": dev["addr"]},
                    "order": 80,
                    "enabled": True,
                }
            )
    return caps
