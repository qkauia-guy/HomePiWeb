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


# 讀取樹莓派上 HAT 的資料，主要有以下幾個原因：

# 1. 自動化設定與驅動程式載入
# 樹莓派作業系統可以根據這些資料，自動辨識連接了哪種 HAT。這樣一來，系統就能夠自動載入正確的驅動程式和軟體模組，使用者就不需要手動安裝和設定，大大簡化了設定過程。舉例來說，如果偵測到某個特定的音效 HAT，系統會自動啟用相關的音訊輸出設定。

# 2. 服務與應用程式相容性
# 許多服務或應用程式需要知道它們正在哪種硬體環境下運作。透過讀取 HAT 的產品名稱和 ID，應用程式可以確保它們只在支援的硬體上執行。這有助於避免因硬體不相容而產生的錯誤。

# 3. 硬體監控與管理
# 這些資料可以用於監控和管理連接的硬體。例如，在工業應用中，可能需要確認特定的感測器或控制板是否正確連接。讀取這些資訊可以提供一個硬體清單，方便管理者確認裝置的狀態。

# 4. 錯誤排除與故障診斷
# 當樹莓派系統出現問題時，這些資料可以幫助診斷故障。如果一個 HAT 無法正常運作，檢查 /proc/device-tree/hat 目錄中的資訊，可以確認系統是否正確辨識了該 HAT，從而縮小問題的範圍。
