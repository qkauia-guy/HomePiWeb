# 偵測並讀取連接到樹莓派上的 DS18B20 溫度感測器
import glob, os

BASE = "/sys/bus/w1/devices"


def detect():
    caps = []
    if not os.path.isdir(BASE):
        return caps
    for path in glob.glob(os.path.join(BASE, "28-*")):  # DS18B20
        sn = os.path.basename(path)
        caps.append(
            {
                "kind": "sensor_ds18b20",
                "name": "溫度探針",
                "slug": f"ds18b20-{sn}",
                "config": {"id": sn},
                "order": 70,
                "enabled": True,
            }
        )
    return caps
