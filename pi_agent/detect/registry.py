# 整合所有裝置偵測方法，並產生一個完整的裝置能力清單
import json, os
from . import i2c, one_wire, hat


def load_manifest(path="config/capabilities.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def discover_all():
    caps = []
    # 1) 模板（GPIO 類靠這份）
    caps.extend(load_manifest())
    # 2) 非侵入式偵測
    for d in (hat, i2c, one_wire):
        try:
            caps.extend(d.detect())
        except Exception as e:
            print("[WARN] detector failed:", d.__name__, e)
    # 3) 去重：以 (kind, slug) 為 key，後來的覆蓋前者
    uniq = {}
    for c in caps:
        key = (c.get("kind"), c.get("slug"))
        uniq[key] = c
    return list(uniq.values())
