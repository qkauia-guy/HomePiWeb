# -*- coding: utf-8 -*-
"""
utils/http.py
封裝與後端 API 溝通的函式：ping / pull / ack
"""

import os
import requests
from typing import Optional

# === 環境設定 ===

# === 掛上自己裝置的 裝置序號 ===
SERIAL = os.getenv("SERIAL", "PI-E239XXXX")
# === 掛上自己裝置的 token ===
TOKEN = os.getenv("TOKEN", "3de6279eae104e0b858b648dc659xxxx")
# === 固定勿修改 ===
API_BASE = os.getenv("API_BASE", "http://172.28.232.36:8800")
PING_PATH = "/api/device/ping/"
PULL_PATH = "/device_pull"
ACK_PATH = "/device_ack"


def ping() -> bool:
    """回報裝置在線"""
    url = f"{API_BASE}{PING_PATH}"
    try:
        r = requests.post(
            url, json={"serial_number": SERIAL, "token": TOKEN}, timeout=5
        )
        r.raise_for_status()
        print("ping ok:", r.json())
        return True
    except Exception as e:
        print("ping err:", e)
        return False


def pull(max_wait: int = 20) -> Optional[dict]:
    """長輪詢拉取下一筆指令"""
    url = f"{API_BASE}{PULL_PATH}"
    try:
        r = requests.post(
            url,
            json={"serial_number": SERIAL, "token": TOKEN, "max_wait": max_wait},
            timeout=max_wait + 5,
        )
        if r.status_code == 204:
            return None
        r.raise_for_status()
        data = r.json()
        print("pull got:", data)
        return data
    except Exception as e:
        print("pull err:", e)
        return None


def ack(req_id: str, ok: bool = True, error: str = ""):
    """回報指令執行結果"""
    url = f"{API_BASE}{ACK_PATH}"
    try:
        r = requests.post(
            url,
            json={
                "serial_number": SERIAL,
                "token": TOKEN,
                "req_id": req_id,
                "ok": ok,
                "error": error,
            },
            timeout=5,
        )
        r.raise_for_status()
        print("ack sent")
    except Exception as e:
        print("ack err:", e)
