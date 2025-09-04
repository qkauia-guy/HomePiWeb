<!-- markdownlint-disable -->

## homepi-camera-hls@.service：攝影機低延遲 HLS 串流服務

這是一個 `systemd` **模板服務檔**，專為樹莓派設計，用於啟動一個低延遲的 **HLS (HTTP Live Streaming)** 攝影機串流。

此服務的主要功能包括：

- **網路就緒後啟動**：確保在有網路連線後才執行。
- **自動化串流**：使用 `rpicam-vid` 捕捉攝影機影像，並透過 `ffmpeg` 將其即時轉換為 HLS 格式。
- **低延遲設定**：透過 `hls_time 0.5` 等參數，將延遲降至最低。
- **檔案管理**：在啟動前自動建立所需目錄並清除舊的串流片段 (`.ts` 檔) 與播放清單 (`.m3u8` 檔)。
- **模板化**：同樣使用 `@` 符號，可為不同使用者啟用。

### 建立與使用服務

1.  **建立服務檔**

    在終端機中建立並編輯此服務檔。
    [homepi-hls@.service 檔案位置：](./systemd檔案/homepi-hls@.service)

    ```
    sudo nano /etc/systemd/system/homepi-camera-hls@.service
    ```

2.  **啟用與啟動**

    **初次建立服務時：**

    ```
    # 重新載入 systemd 設定
    sudo systemctl daemon-reload

    # 設定開機自動啟動（將 <username> 替換為樹梅派 User Name）
    sudo systemctl enable homepi-camera-hls@<username>.service

    # 立即啟動服務
    sudo systemctl start homepi-camera-hls@<username>.service
    ```

    **修改服務檔後：**

    ```
    sudo systemctl daemon-reload
    sudo systemctl restart homepi-camera-hls@<username>.service
    ```

3.  **檢查服務狀態**

    確認服務狀態與日誌。

    ```
    sudo systemctl status homepi-camera-hls@<username>.service
    ```

### 服務檔設定內容

```int
[Unit]
# 服務的描述，會顯示在 `systemctl status` 等指令中。%i 會被替換為使用者名稱。
Description=HomePi Camera HLS Stream (Low-Latency TS) for user %i

# 指定服務必須在網路連線完全建立後才啟動。
After=network-online.target

# 同樣表示對網路的依賴，但這是軟性依賴，即使 network-online.target 失敗，服務仍會嘗試啟動。
Wants=network-online.target


[Service]
# 服務類型。simple 表示 ExecStart 指定的程序就是主要服務程序。
Type=simple

# 以指定的使用者身分執行此服務。%i 是模板變數，代表 `@` 後面的字串。
User=%i
# 以指定的使用者群組身分執行。
Group=%i

# 將服務的執行使用者加入 'video' 群組，使其有權限存取攝影機硬體 (如 /dev/video*）。
SupplementaryGroups=video

# 設定服務的工作目錄。所有相對路徑都會基於此目錄。
WorkingDirectory=/home/%i/pi_agent/stream

# 指定要載入的環境變數檔案。服務啟動時會讀取此檔案中的變數。
EnvironmentFile=/home/%i/pi_agent/.env

# 設定額外的環境變數，這裡用來確保 Python 輸出不被緩衝 (雖然此服務主要用 bash)。
Environment=PYTHONUNBUFFERED=1

# --- 啟動前置作業 ---
# 在主程序 (ExecStart) 執行前執行的指令。
# -p 參數確保如果目錄已存在，則不會報錯。
ExecStartPre=/usr/bin/mkdir -p /home/%i/pi_agent/stream
# 刪除 ffmpeg 可能產生的暫存播放清單檔。
ExecStartPre=/usr/bin/rm -f /home/%i/pi_agent/stream/index.m3u8.tmp
# 刪除舊的 HLS 播放清單檔，確保每次啟動都是全新的。
ExecStartPre=/usr/bin/rm -f /home/%i/pi_agent/stream/index.m3u8
# 刪除所有舊的影像片段檔案 (*.ts)，避免播放器讀到過時的內容。
ExecStartPre=/usr/bin/rm -f /home/%i/pi_agent/stream/seg_*.ts

# --- 主要執行指令 ---
# 使用 bash 執行一個包含管線 (|) 的複合指令。
# -lc: 'l' 使其像登入 shell 一樣執行，'c' 後面接要執行的指令字串。
# set -o pipefail: 確保管線中任何一個指令失敗，整個指令都會被視為失敗，觸發 Restart 機制。
ExecStart=/usr/bin/bash -lc 'set -o pipefail; \
  # --- 步驟 1: 使用 rpicam-vid 擷取攝影機影像 ---
  /usr/bin/rpicam-vid -t 0 \
    --width 1280 --height 720 --framerate 30 \
    --codec h264 --profile baseline --level 4.0 \
    --intra 15 --inline --nopreview \
    --libav-format h264 -o - \
  | \
  # --- 步驟 2: 使用 ffmpeg 處理影像流並產生 HLS ---
  /usr/bin/ffmpeg -loglevel warning -fflags +genpts -use_wallclock_as_timestamps 1 \
    -f h264 -i - -c:v copy -an \
    -f hls -hls_time 0.5 -hls_list_size 3 -start_number 1 \
    -hls_flags delete_segments+append_list+program_date_time+independent_segments+temp_file \
    -hls_segment_filename /home/%i/pi_agent/stream/seg_%%05d.ts \
    /home/%i/pi_agent/stream/index.m3u8'

# --- 服務重啟與停止策略 ---
# 當服務非正常退出時 (例如發生錯誤)，自動重啟。
Restart=on-failure
# 重啟前等待 2 秒。
RestartSec=2s
# 停止服務時，發送 SIGINT (相當於 Ctrl+C) 信號給主程序，讓其優雅地關閉。
KillSignal=SIGINT
# 如果程序在 10 秒內沒有回應 SIGINT，則強制終止。
TimeoutStopSec=10

# --- 安全性設定 ---
# 禁止服務程序獲取新的權限。
NoNewPrivileges=yes
# 為服務建立一個私有的 /tmp 目錄，與系統隔離。
PrivateTmp=yes
# 保護系統目錄 (/usr, /boot, /etc) 不被服務寫入，設為唯讀。
ProtectSystem=full
# 明確指定服務唯一可讀寫的路徑。這是個白名單，其他路徑預設為唯讀。
ReadWritePaths=/home/%i/pi_agent/stream


[Install]
# 指定此服務應在哪個 target 下啟用。multi-user.target 是標準的多使用者模式。
# 執行 `systemctl enable` 時，systemd 會在此 target 的 .wants 目錄下建立符號連結。
WantedBy=multi-user.target
```

#### [上一步:04 HTTP 代理程式(homepi-http-agent.service)](<04HTTP代理程式(homepi-http-agent.service).md>)

#### [06 啟動輕量級的網頁伺服器(homepi-hls-www.service)](<06啟動輕量級的網頁伺服器(homepi-hls-www.service).md>)
