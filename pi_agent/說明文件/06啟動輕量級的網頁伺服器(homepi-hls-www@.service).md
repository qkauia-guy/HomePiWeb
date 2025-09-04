<!-- markdownlint-disable -->

# HomePi 系統服務 (systemd) 完整設定

這份文件整合了 HomePi 專案所需的三個核心 `systemd` 服務，讓您可以在樹莓派上實現代理程式、低延遲攝影機串流，以及網頁伺服器等功能。

---

## 1. homepi-agent@.service：樹莓派代理程式模板服務

這是一個 `systemd` **模板服務檔**，它的主要功能是在樹莓派開機後，自動以背景程式的方式啟動您的 **HomePi HTTP 代理程式**。

這個服務檔會告訴樹莓派的系統：

- **當網路就緒後**，啟動此服務。
- 服務會以**指定使用者**（如 `qkauia`）的身份運行，並執行 `pi_agent` 資料夾中的 `http_agent.py` 腳本。
- 自動載入 `.env` 環境變數檔，確保日誌即時輸出，並在程式停止時自動重新啟動。

這個服務檔是一個**模板**，只需在啟用服務時指定使用者名稱，即可為不同使用者重複使用此設定。

### 建立與使用服務

1.  **建立服務檔**

    在終端機中建立並編輯服務檔，建議在其他編輯器中完成編輯後再貼上。
    [homepi-hls-www@.service 檔案位置：](./systemd檔案/homepi-hls-www@.service)

    ```
    sudo nano /etc/systemd/system/homepi-agent@.service
    ```

2.  **啟用與啟動**

    **初次建立服務時：**

    ```
    # 重新載入 systemd 設定
    sudo systemctl daemon-reload

    # 設定開機自動啟動（將 <username> 替換為樹梅派 User Name）
    sudo systemctl enable homepi-agent@<username>.service

    # 立即啟動服務
    sudo systemctl start homepi-agent@<username>.service
    ```

    **修改服務檔後：**

    ```
    sudo systemctl daemon-reload
    sudo systemctl restart homepi-agent@<username>.service
    ```

3.  **檢查服務狀態**

    確認服務狀態為綠色的 `active (running)`，且無錯誤。

    ```
    sudo systemctl status homepi-agent@<username>.service
    ```

### 服務檔設定內容 (含註解)

```int
[Unit]

服務的描述名稱，%i 會被替換為使用者名稱。
Description=HomePi HTTP Agent for user %i

指定服務在網路就緒後啟動。
After=network-online.target
Wants=network-online.target

[Service]

服務型態：simple 表示 ExecStart 的程序就是主程序。
Type=simple

使用者與群組設定，%i 代表模板變數。
User=%i
Group=%i

啟動時的工作目錄。
WorkingDirectory=/home/%i/pi_agent

從 .env 載入環境變數，路徑前的 '-' 表示即使檔案不存在也不會報錯。
EnvironmentFile=-/home/%i/pi_agent/.env

額外環境變數設定。
Environment=PYTHONUNBUFFERED=1
Environment=HOME=/home/%i

啟動的主程式。
ExecStart=/usr/bin/python3 -u /home/%i/pi_agent/http_agent.py

服務重啟策略：無論如何都自動重啟。
Restart=always

重啟間隔 3 秒。
RestartSec=3

停止服務的超時時間。
TimeoutStopSec=15

停止服務時只終止主程序。
KillMode=process

安全性設定。
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full

日誌輸出：標準輸出到 journald，標準錯誤繼承。
StandardOutput=journal
StandardError=inherit

[Install]

指定開機時自動啟動的目標。
WantedBy=multi-user.target
```

#### [上一步:05 HLS 影片串流服務(homepi-hls@.service)](<05HLS影片串流服務(homepi-hls@.service).md>)

#### [下一步:07 排程服務(homepi-scheduler@.service)](<07排程服務(homepi-scheduler@.service).md>)
