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


# I2C 的本質就是一種簡單、高效、只需要兩條線的點對多點通訊方式，它讓不同功能的電子零件能夠有條不紊地協同工作。

# 你可以把它想成一條雙向的公車路線，上面只有兩條線路：

# SCL (Serial Clock Line)：這是時脈線，就像司機發出的節拍器。它負責同步所有裝置的資料傳輸速度，確保每個裝置都能在正確的時間點發送和接收資訊。
# SDA (Serial Data Line)：這是資料線，就像公車本身。所有裝置都用這條線來傳送和接收資料。這條線是雙向的，所以資料可以從一端流向另一端。

# 核心運作方式
# 主從架構：I2C 系統裡，只有一個主機 (Master) 裝置（通常是你的樹莓派或 Arduino），它負責發起通訊、控制時脈。而其他所有的裝置都是從機 (Slave)，它們只能被動地等待主機呼叫。

# 地址辨識：每個從機都有一個獨特的地址。主機要和某個從機對話時，會先廣播這個從機的地址。當從機聽到自己的地址被叫到，它就會回應，並準備好進行資料交換。

# scan_i2c_bus 函式
# 這個函式負責掃描指定的 I2C 總線，找出所有有回應的裝置位址。
