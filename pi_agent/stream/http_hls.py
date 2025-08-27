# /home/qkauia/pi_agent/stream/http_hls.py
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
import os


class CORSRequestHandler(SimpleHTTPRequestHandler):
    # 用 HTTP/1.1（較穩 + 支援 206 partial content）
    protocol_version = "HTTP/1.1"

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        # 允許 Range 頭，避免 preflight 卡住
        self.send_header(
            "Access-Control-Allow-Headers",
            "Origin, Accept, Content-Type, Range, Referer, User-Agent",
        )
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        # 避免快取舊的 m3u8
        self.send_header("Cache-Control", "no-store, max-age=0")
        return super().end_headers()

    def do_OPTIONS(self):
        # 回應預檢要求
        self.send_response(204)
        self.end_headers()

    def guess_type(self, path):
        if path.endswith(".m3u8"):
            return "application/vnd.apple.mpegurl"
        if path.endswith(".ts"):
            return "video/mp2t"
        return super().guess_type(path)


if __name__ == "__main__":
    os.chdir("/home/qkauia/pi_agent/stream")
    TCPServer.allow_reuse_address = True
    with TCPServer(("0.0.0.0", 8088), CORSRequestHandler) as httpd:
        httpd.serve_forever()
