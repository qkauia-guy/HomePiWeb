<!-- markdownlint-disable -->

## 4. homepi-scheduler@.service：排程任務管理器

這是一個 `systemd` **模板服務**，用於執行一個背景的排程管理器。

- **功能**：定期從遠端拉取排程、執行預定動作、處理自動開關燈等自動化任務。
- **執行方式**：作為一個 Python 模組 (`utils.scheduler`) 執行。
- **可靠性**：發生錯誤時會自動重啟。

### 建立與使用服務

1.  **建立服務檔**
    [homepi-scheduler@.service 檔案位置：](./systemd檔案/homepi-scheduler@.service)

    ```
    sudo nano /etc/systemd/system/homepi-scheduler@.service
    ```

2.  **啟用與啟動**

    ```
    # 重新載入 systemd 設定
    sudo systemctl daemon-reload

    # 設定開機自動啟動（將 <username> 替換為樹梅派 User Name）
    sudo systemctl enable homepi-scheduler@<username>.service

    # 立即啟動服務
    sudo systemctl start homepi-scheduler@<username>.service
    ```

### 服務檔設定內容

```int
[Unit]

服務描述，%i 會被替換為使用者名稱。
Description=HomePi Scheduler (pull schedules, run actions, auto-light) for user %i

依賴網路連線。
After=network-online.target
Wants=network-online.target

[Service]

服務類型：simple。
Type=simple

以指定使用者身分執行。
User=%i
Group=%i

設定工作目錄。
WorkingDirectory=/home/%i/pi_agent

載入環境變數。
EnvironmentFile=/home/%i/pi_agent/.env
Environment=PYTHONUNBUFFERED=1

--- 主要執行指令 ---
使用 -m 參數執行一個 Python 模組。
這會將 utils 目錄下的 scheduler.py 當作腳本執行。
ExecStart=/usr/bin/python3 -m utils.scheduler

--- 服務重啟與停止策略 ---
當服務非正常退出時 (發生錯誤) 自動重啟。
Restart=on-failure

重啟間隔 2 秒。
RestartSec=2s

停止服務時，會終止此服務控制群組下的所有程序。
KillMode=control-group

--- 日誌輸出 ---
將標準輸出和標準錯誤都導向到 systemd 的 journald 日誌系統。
StandardOutput=journal
StandardError=journal

[Install]

指定開機時自動啟動的目標。
WantedBy=multi-user.target
```

#### [上一步:06 啟動輕量級的網頁伺服器(homepi-hls-www@.service)](<06啟動輕量級的網頁伺服器(homepi-hls-www@.service).md>)
