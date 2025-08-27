# -*- coding: utf-8 -*-
# 導入程式所需的標準函式庫
import os, socket, subprocess
from pathlib import Path


# 封裝底層的子程序執行命令
def _run(cmd):
    # 執行指令並捕獲輸出，將輸出以文字格式回傳
    return subprocess.run(cmd, capture_output=True, text=True)


# 取得本機 IP 位址的輔助函式
def _ip():
    try:
        # 建立一個 UDP socket，並連線到外部網址以取得本機 IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # 如果發生錯誤，回傳本機位址
        return "127.0.0.1"


# Camera 類別，用來表示一個相機設備
class Camera:
    # 類別的初始化函式
    def __init__(self, name: str, slug: str, config: dict):
        # 設備的名稱和簡稱（唯一識別碼）
        self.name = name
        self.slug = slug
        # 讀取傳入的設定字典
        self.cfg = config or {}
        # 服務名稱，預設為 homepi-hls
        self.service = self.cfg.get("service", "homepi-hls")
        # HLS 伺服器的 IP，如果設定中沒有則使用本機 IP
        self.hls_host = self.cfg.get("hls_host") or _ip()
        # HLS 伺服器的埠號，預設為 8088
        self.hls_port = int(self.cfg.get("hls_port", 8088))
        # HLS 串流的相對路徑，預設為 /index.m3u8
        self.hls_path = self.cfg.get("hls_path", "/index.m3u8")

    # 啟動相機服務
    def start(self):
        # 執行 sudo systemctl start homepi-hls 命令
        _run(["sudo", "systemctl", "start", self.service])

    # 停止相機服務
    def stop(self):
        # 執行 sudo systemctl stop homepi-hls 命令
        _run(["sudo", "systemctl", "stop", self.service])

    # 檢查服務的運行狀態
    def status(self) -> dict:
        # 執行 systemctl is-active 命令來檢查服務是否在運行
        r = _run(["systemctl", "is-active", self.service])
        # 判斷指令輸出是否為 'active'，以確定服務是否運行中
        running = (r.stdout or r.stderr).strip() == "active"
        # 組合出完整的 HLS 串流 URL
        url = f"http://{self.hls_host}:{self.hls_port}{self.hls_path}"
        # 回傳包含運行狀態和串流 URL 的字典
        return {"running": running, "hls_url": url}


# --- 舊介面的包裝，讓 http_agent.py 仍可呼叫 camera.stream_start/stop ---
# 這個區塊提供了舊版本程式碼的相容性，方便過渡
def stream_start(service: str | None = None):
    svc = service or "homepi-hls"
    return _run(["sudo", "systemctl", "start", svc])


def stream_stop(service: str | None = None):
    svc = service or "homepi-hls"
    return _run(["sudo", "systemctl", "stop", svc])


def start_hls(service: str | None = None):
    return stream_start(service)


def stop_hls(service: str | None = None):
    return stream_stop(service)
