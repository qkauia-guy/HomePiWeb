# 引入 Python 內建的模組
from http.server import SimpleHTTPRequestHandler  # 提供基本的 HTTP 檔案服務功能
from socketserver import TCPServer  # 用於建立 TCP 伺服器的基礎框架
import os  # 用於和作業系統互動，例如檔案路徑操作
import posixpath  # 用於處理符合 POSIX 標準的路徑（URL-like）
import urllib.parse  # 用於解析 URL

# --- 全域設定 ---
# 設定 HLS 串流檔案（.m3u8 和 .ts）所在的根目錄
# 伺服器會將此目錄作為提供檔案的基礎路徑
HLS_ROOT = os.path.expanduser("~/pi_agent/stream")


# --- 自訂請求處理器 ---
# 繼承自 SimpleHTTPRequestHandler，並在其基礎上增加特定功能
class CORSRequestHandler(SimpleHTTPRequestHandler):
    """
    這個處理器繼承了 Python 原生的簡易 HTTP 請求處理器，
    並加入了 HLS 串流所需的關鍵功能：
    1. CORS 跨域支援：允許任何網頁前端（如 hls.js）存取此伺服器的資源。
    2. 正確的 MIME 類型：確保 .m3u8 和 .ts 檔案被瀏覽器正確識別。
    3. m3u8 播放列表的快取控制：強制瀏覽器每次都請求最新的播放列表。
    4. 安全的路徑處理：防止惡意使用者透過 URL 存取伺服器上的任意檔案。
    """

    # --- 私有輔助方法：設定 CORS 相關的 HTTP Headers ---
    def _set_cors(self):
        """
        為回應加上 CORS (Cross-Origin Resource Sharing) 標頭。
        這是讓不同網域的網頁能夠透過 JavaScript 存取此伺服器資源的關鍵。
        """
        # 允許來自任何來源（網域）的請求
        self.send_header("Access-Control-Allow-Origin", "*")

        # 允許 hls.js 等播放器在請求中附加的特定標頭，特別是 'Range' 用於影片跳轉
        self.send_header(
            "Access-Control-Allow-Headers", "*,Range,Origin,Accept,Content-Type"
        )

        # 宣告此伺服器允許的 HTTP 方法
        self.send_header("Access-Control-Allow-Methods", "GET,HEAD,OPTIONS")

        # 允許前端 JavaScript 讀取的回應標頭，如 'Content-Length' 用於得知檔案大小
        self.send_header(
            "Access-Control-Expose-Headers",
            "Content-Length,Accept-Ranges,Content-Range",
        )

        # 瀏覽器可以快取 CORS 預檢請求（OPTIONS）的結果 10 分鐘（600秒），
        # 避免對同一個資源重複發送預檢請求
        self.send_header("Access-Control-Max-Age", "600")

    # --- 處理 CORS 預檢請求 (Preflight Request) ---
    def do_OPTIONS(self):
        """
        處理瀏覽器在發送實際請求（如 GET）前，為確認 CORS 權限而發送的 OPTIONS 請求。
        """
        # 回應 200 OK，表示伺服器理解此請求
        self.send_response(200, "OK")
        # 加上 CORS 標頭，告知瀏覽器允許跨域存取
        self._set_cors()
        # 結束標頭寫入
        self.end_headers()

    # --- 覆寫方法：修正 HLS 檔案的 Content-Type ---
    def guess_type(self, path):
        """
        覆寫父類別的方法，以正確識別 HLS 串流所需的特殊 MIME 類型。
        """
        # 如果檔案是 .m3u8 播放列表，設定其 MIME 類型為 HLS 專用的格式
        if path.endswith(".m3u8"):
            return "application/vnd.apple.mpegurl"
        # 如果檔案是 .ts 影片分段，設定其 MIME 類型為 MPEG-2 Transport Stream
        if path.endswith(".ts"):
            return "video/mp2t"
        # 其他檔案類型則沿用父類別的預設判斷邏輯
        return super().guess_type(path)

    # --- 覆寫方法：在傳送檔案前回應加上標頭 ---
    def end_headers(self):
        """
        覆寫父類別的方法。此方法在所有 HTTP 標頭計算完畢、即將送出前被呼叫。
        我們利用這個時機點來動態加入我們的自訂標頭。
        """
        # 為所有 GET/HEAD 請求都加上 CORS 標頭
        self._set_cors()

        # 特別處理 .m3u8 播放列表檔案
        if self.path.endswith(".m3u8"):
            # .m3u8 檔案會持續更新，必須告訴瀏覽器和中間代理伺服器「不要快取」此檔案，
            # 才能確保播放器能拿到最新的影片分段列表。
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")  # 相容舊版 HTTP/1.0

        # 呼叫父類別的原始 end_headers 方法，以完成標頭的發送
        super().end_headers()

    # --- 覆寫方法：安全的將 URL 路徑轉換為檔案系統路徑 ---
    def translate_path(self, path):
        """
        覆寫父類別的方法，提供一個更安全的路徑轉換機制。
        目的是防止所謂的「目錄遍歷攻擊」(Directory Traversal Attack)，
        例如避免有人用 ../../ 等方式存取到 HLS_ROOT 以外的檔案。
        """
        # 1. 解析 URL，並只取路徑部分，忽略 querystring (?foo=bar)
        path = urllib.parse.urlsplit(path).path
        # 2. 解碼 URL 編碼（例如 %20 轉為空格），並正規化路徑（移除多餘的 /）
        path = posixpath.normpath(urllib.parse.unquote(path))

        # 3. 將路徑分割成各個部分，並過濾掉空字串、'.'（當前目錄）和 '..'（上層目錄）
        #    這是防止目錄遍歷的核心步驟。
        parts = [p for p in path.split("/") if p and p not in (".", "..")]

        # 4. 從我們設定的 HLS_ROOT 開始，安全地逐一組合路徑
        full = HLS_ROOT
        for p in parts:
            full = os.path.join(full, p)

        # 5. 回傳最終計算出的、安全的、絕對的檔案系統路徑
        return full


# --- 主程式進入點 ---
# 確保這段程式碼只在直接執行此 .py 檔案時才會運行
if __name__ == "__main__":
    # 將目前的工作目錄切換到 HLS 檔案的根目錄
    # 這是因為 SimpleHTTPRequestHandler 的預設行為是從當前工作目錄提供檔案
    os.chdir(HLS_ROOT)

    # 允許伺服器地址重用。這樣在重啟伺服器時，可以立即綁定同一個埠號，
    # 無需等待作業系統釋放，方便開發和除錯。
    TCPServer.allow_reuse_address = True

    # 建立一個 TCPServer 實例
    # - 綁定在 "0.0.0.0" 表示監聽所有可用的網路介面（不只是 localhost）
    # - 監聽 8088 埠號
    # - 使用我們上面自訂的 CORSRequestHandler 來處理所有傳入的請求
    with TCPServer(("0.0.0.0", 8088), CORSRequestHandler) as httpd:
        print("HLS static server listening on :8088, root =", HLS_ROOT)
        # 啟動伺服器，使其永久運行，直到手動中斷（例如按下 Ctrl+C）
        httpd.serve_forever()
