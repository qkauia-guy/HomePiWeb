# -*- coding: utf-8 -*-
"""
utils/http.py

這個模組封裝了與後端 API 溝通的函式，主要用於物聯網 (IoT) 裝置。
它提供了一系列功能，讓裝置可以和伺服器進行「心跳」、「拉取指令」、
「回報執行結果」和「排程管理」等操作。
"""

import os
import requests
from typing import Optional, Union
from dotenv import load_dotenv

# 從 .env 檔案載入環境變數。這是一個很好的資安實踐，
# 可以避免將敏感資訊（如裝置序列號、Token）硬寫在程式碼中。
load_dotenv()

# --- 環境設定 ---
# 這些變數會從 .env 檔案中讀取。如果 .env 中找不到，則使用後面的預設值。
# 例如：os.getenv("SERIAL", "default-serial") 會先找名為 SERIAL 的環境變數，
# 找不到的話就用 "default-serial" 這個字串。

# 掛上自己裝置的 裝置序號
SERIAL = os.getenv("SERIAL", "default-serial")
# 掛上自己裝置的 token
TOKEN = os.getenv("TOKEN", "default-token")
# 後端 API 的基礎網址，通常是固定不變的。
API_BASE = os.getenv("API_BASE", "http://172.28.104.118:8888/")
# API_BASE = os.getenv("API_BASE", "http://172.28.232.36:8800")
# API 接口路徑
PING_PATH = "/api/device/ping/"
PULL_PATH = "/api/device/pull/"
ACK_PATH = "/api/device/ack/"
SCHEDULES_PATH = "/api/device/schedules/"
SCHEDULE_ACK_PATH = "/api/device/schedule_ack/"

# 建立一個 requests session 來重用 TCP 連線，可以提升效能。
_session = requests.Session()
# 在所有請求的標頭中設定 Content-Type，讓伺服器知道我們發送的是 JSON 格式。
_session.headers.update({"Content-Type": "application/json"})


def _print_resp(prefix: str, r: requests.Response) -> None:
    """
    內部函式：格式化並印出 HTTP 請求的回應，方便除錯。
    它會嘗試將伺服器回傳的資料解析為 JSON，失敗則印出原始文字。
    """
    try:
        data = r.json()
        print(f"{prefix}: HTTP {r.status_code} ->", data)
    except Exception:
        print(f"{prefix}: HTTP {r.status_code} ->", r.text)


def ping(extra: Optional[dict] = None) -> bool:
    """
    向伺服器發送「心跳」訊號，表明裝置還活著。
    可以選擇性地附帶裝置的當前狀態 (caps/state) 等額外資訊。

    Args:
        extra: 包含額外資訊的字典。

    Returns:
        bool: 如果心跳成功回傳 True，否則為 False。
    """
    url = f"{API_BASE}{PING_PATH}"
    payload = {"serial_number": SERIAL, "token": TOKEN}
    if extra:
        payload.update(extra)
        payload["extra"] = extra
    try:
        r = _session.post(url, json=payload, timeout=5)
    except Exception as e:
        print("ping err (conn):", e)
        return False

    if r.ok:
        _print_resp("ping ok", r)
        return True

    _print_resp("ping err", r)
    return False


def pull(max_wait: int = 20) -> Optional[dict]:
    """
    執行長輪詢（long polling），向伺服器拉取下一筆要執行的指令。

    Args:
        max_wait: 等待伺服器回應的最長時間（秒）。

    Returns:
        Optional[dict]: 如果有新指令，則回傳包含指令內容的字典；
                     如果沒有新指令（HTTP 204）或發生錯誤，則回傳 None。
    """
    url = f"{API_BASE}{PULL_PATH}"
    try:
        r = _session.post(
            url,
            json={"serial_number": SERIAL, "token": TOKEN, "max_wait": max_wait},
            timeout=max_wait + 5,
        )
    except Exception as e:
        print("pull err (conn):", e)
        return None

    if r.status_code == 204:
        # HTTP 204 (No Content) 代表目前沒有指令
        return None
    if not r.ok:
        _print_resp("pull err", r)
        return None

    try:
        data = r.json()
    except Exception:
        print("pull err: bad json:", r.text)
        return None

    print("pull got:", data)
    return data


def ack(req_id: str, ok: bool = True, error: str = "", state: Optional[dict] = None):
    """
    回報指令的執行結果給伺服器。

    Args:
        req_id: 指令的唯一識別碼。
        ok: 布林值，表示指令是否成功執行。
        error: 如果執行失敗，提供錯誤訊息。
        state: 可選擇性地附帶裝置的最新狀態。
    """
    print(
        f"[DEBUG] ack 開始發送: req_id={req_id}, ok={ok}, error='{error}', state={state}"
    )
    url = f"{API_BASE}{ACK_PATH}"
    payload = {
        "serial_number": SERIAL,
        "token": TOKEN,
        "req_id": req_id,
        "ok": ok,
        "error": error,
    }
    if state is not None:
        payload["state"] = state

    print(f"[DEBUG] ack payload: {payload}")
    print(f"[DEBUG] ack URL: {url}")

    try:
        r = _session.post(url, json=payload, timeout=5)
        print(f"[DEBUG] ack HTTP 回應: status_code={r.status_code}")
    except Exception as e:
        print(f"[DEBUG] ack 連線錯誤: {e}")
        print("ack err (conn):", e)
        return

    if not r.ok:
        print(f"[DEBUG] ack 失敗: HTTP {r.status_code}")
        _print_resp("ack err", r)
    else:
        print(f"[DEBUG] ack 成功: HTTP {r.status_code}")
        print("ack ok")


def fetch_schedules() -> list:
    """
    向伺服器請求未來的排程清單。

    Returns:
        list: 包含所有排程的字典清單。如果發生錯誤，則回傳空清單。
    """
    url = f"{API_BASE}{SCHEDULES_PATH}"
    payload = {"serial_number": SERIAL, "token": TOKEN}
    try:
        r = _session.post(url, json=payload, timeout=5)
    except Exception as e:
        print("fetch_schedules err (conn):", e)
        return []

    if not r.ok:
        _print_resp("fetch_schedules err", r)
        return []

    try:
        data = r.json()
    except Exception:
        print("fetch_schedules err: bad json:", r.text)
        return []

    if not data.get("ok"):
        print("fetch_schedules err:", data)
        return []

    items = data.get("items") or []
    return items


def schedule_ack(schedule_id: int, ok: bool, error: str = ""):
    """
    回報排程的執行結果給伺服器。

    Args:
        schedule_id: 排程的唯一識別碼。
        ok: 布林值，表示排程是否成功執行。
        error: 如果執行失敗，提供錯誤訊息。
    """
    url = f"{API_BASE}{SCHEDULE_ACK_PATH}"
    payload = {
        "serial_number": SERIAL,
        "token": TOKEN,
        "schedule_id": int(schedule_id),
        "ok": ok,
        "error": error,
    }
    try:
        r = _session.post(url, json=payload, timeout=5)
    except Exception as e:
        print("schedule_ack err (conn):", e)
        return

    if not r.ok:
        _print_resp("schedule_ack err", r)
    else:
        print("schedule_ack ok")
