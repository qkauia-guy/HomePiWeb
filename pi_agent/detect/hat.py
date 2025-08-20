# 讀取樹梅派資訊
import os

DT = "/proc/device-tree/hat"


def _read_str(p):
    try:
        with open(p, "rb") as f:
            return f.read().decode("utf-8").rstrip("\x00")
    except Exception:
        return ""


def detect():
    if not os.path.isdir(DT):
        return []
    product = _read_str(os.path.join(DT, "product"))
    vendor = _read_str(os.path.join(DT, "vendor"))
    pid = _read_str(os.path.join(DT, "product_id"))
    if not product:
        return []
    return [
        {
            "kind": "hat",
            "name": product,
            "slug": f"hat-{pid or 'unknown'}",
            "config": {"vendor": vendor, "product_id": pid},
            "order": 95,
            "enabled": True,
        }
    ]
