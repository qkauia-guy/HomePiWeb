<!-- markdownlint-disable -->

## 3. homepi-hls-www@.service：HLS 靜態網頁伺服器

這是一個 `systemd` **模板服務**，用於啟動一個簡易的 Python 靜態網頁伺服器，專門提供 HLS 串流所需的 `.m3u8` 和 `.ts` 檔案。

- **依賴管理**：此服務會等待攝影機串流服務 (`homepi-camera-hls@.service`) 啟動後才執行。
- **CORS 支援**：執行的 Python 腳本應內建 CORS (跨來源資源共用) 支援，允許網頁從不同網域存取串流。
- **自動重啟**：服務會持續運行，並在意外停止時自動重啟。

### 建立與使用服務

1.  **建立服務檔**
    [homepi-hls-www@.service 檔案位置：](./systemd檔案/homepi-hls-www@.service)

    ```
    sudo nano /etc/systemd/system/homepi-hls-www@.service
    ```

2.  **啟用與啟動**

    ```
    # 重新載入、啟用並啟動服務
    sudo systemctl daemon-reload

     # 設定開機自動啟動（將 <username> 替換為樹梅派 User Name）
    sudo systemctl enable homepi-hls-www@<username>.service

    # 立即啟動服務
    sudo systemctl start homepi-hls-www@<username>.service
    ```

3.  **檢查服務狀態**

    ```
    sudo systemctl status homepi-hls-www@<username>.service
    ```

### 服務檔設定內容

```int
[Unit]

服務的描述，清楚說明其功能。
Description=HomePi HLS static web server (CORS) on :8088

--- 服務依賴設定 ---
指定此服務必須在網路就緒、且攝影機串流服務啟動之後，才能啟動。
注意：這裡的 homepi-hls.service 應為 homepi-camera-hls@%i.service 才能正確對應模板
After=network-online.target homepi-camera-hls@%i.service

Wants=network-online.target

[Service]

服務類型：simple。
Type=simple

使用者與群組設定。
User=%i
Group=%i

載入環境變數檔案。
EnvironmentFile=/home/%i/pi_agent/.env

--- 主要執行指令 ---
執行 serve_hls.py 腳本，啟動網頁伺服器。
ExecStart=/usr/bin/python3 /home/%i/pi_agent/serve_hls.py

--- 服務重啟策略 ---
無論如何都自動重啟。
Restart=always

重啟間隔 1 秒。
RestartSec=1

[Install]
WantedBy=multi-user.target
```

#### [上一步:05 HLS 影片串流服務(homepi-hls@.service)](<05HLS影片串流服務(homepi-hls@.service).md>)

#### [下一步:07 排程服務(homepi-scheduler@.service)](<07排程服務(homepi-scheduler@.service).md>)
