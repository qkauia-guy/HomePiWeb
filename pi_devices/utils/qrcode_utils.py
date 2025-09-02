import qrcode  # 引入 qrcode 套件，用來生成 QR Code 圖像
import base64  # 引入 base64 模組，用來做編碼（圖檔轉成文字字串）
import os
from io import BytesIO  # 引入 BytesIO，用來當作記憶體中的二進位資料流容器

from django.conf import settings


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


def generate_device_qrcode(device):
    """
    根據 device 產生 QRCode 圖片，並儲存為 PNG 檔案在 static/qrcodes/ 下。
    圖片檔名為：<serial_number>.png
    """
    register_url = f"http://172.28.232.36:8800/register/?serial={device.serial_number}&code={device.verification_code}"  # ZeroTier IP
    # register_url = f"http://192.168.0.100:8800/register/?serial={device.serial_number}&code={device.verification_code}"  # 宿舍 IP
    # register_url = f"http://192.168.67.42:8800/register/?serial={device.serial_number}&code={device.verification_code}"  # 406 教室 IP
    # register_url = f"http://192.168.197.104:8800/register/?serial={device.serial_number}&code={device.verification_code}"  # home
    qr_img = qrcode.make(register_url)

    qr_dir = os.path.join(settings.BASE_DIR, "static", "qrcodes")
    os.makedirs(qr_dir, exist_ok=True)

    file_path = os.path.join(qr_dir, f"{device.serial_number}.png")
    qr_img.save(file_path)

    return file_path
