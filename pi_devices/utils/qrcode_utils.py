import qrcode  # 引入 qrcode 套件，用來生成 QR Code 圖像
import base64  # 引入 base64 模組，用來做編碼（圖檔轉成文字字串）
from io import BytesIO  # 引入 BytesIO，用來當作記憶體中的二進位資料流容器


def generate_qr_code_base64(url: str) -> str:
    """
    給定一個 URL 字串，產生對應的 QR Code 圖片，並回傳經 base64 編碼的圖片字串，
    回傳格式是可直接嵌入 HTML img 標籤的 data URI。
    """
    qr = qrcode.make(url)  # 使用 qrcode 套件快速生成 QR Code 圖像物件，內容是輸入的 url

    buffered = BytesIO()  # 建立一個 BytesIO 記憶體緩衝區（像檔案，但存在記憶體內）
    qr.save(
        buffered, format="PNG"
    )  # 將前面建立的 QR Code 圖像物件以 PNG 格式存入這個記憶體緩衝區

    img_base64 = base64.b64encode(buffered.getvalue()).decode()
    # 讀取緩衝區內的二進位 PNG 圖檔資料（buffered.getvalue()）
    # 利用 base64 編碼方法將二進位資料轉成 base64 字串
    # decode() 把編碼結果由 bytes 轉成普通字串（str）

    # 回傳一個完整的 Data URI，格式為：
    # "data:image/png;base64,<base64編碼的圖像資料>"
    # 這字串可以直接放入 HTML 的 <img src="這裡"> 標籤顯示圖片
    return f"data:image/png;base64,{img_base64}"
