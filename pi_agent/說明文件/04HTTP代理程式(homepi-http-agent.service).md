<!-- markdownlint-disable -->

#### homepi-http-agent.service：

這是一個 `systemd` 服務檔，它的主要功能是在樹莓派開機後，自動以背景程式的方式啟動您的 **HomePi HTTP 代理程式**。

> 簡單來說，這個服務檔告訴樹莓派的系統：
>
> - **當網路就緒後**，請執行這個服務。
> - **服務會啟動一個 Python 程式**，這個程式會：
>   - 以指定的使用者（`qkauia`）身份運行。
>   - 在指定的目錄（`/home/qkauia/pi_agent`）中執行 `http_agent.py` 腳本。
>   - 設定數個環境變數，例如 `PYTHONUNBUFFERED=1`（禁用 Python 緩衝，確保日誌即時顯示）和 `LED_PIN=17`（指定 LED 燈腳位）。
> - 如果程式因為任何原因停止，請**自動重新啟動**它，以確保服務持續運行。

---

##### 建立流程與注意事項

1.  **創建服務檔**：在終端機中，使用 `sudo nano` 指令來建立並編輯服務檔。

    ```bash
    sudo nano /etc/systemd/system/homepi-agent.service
    ```

    由於 `nano` 在處理多行程式碼時較難編輯，通常都建議在 `vscode` 中編輯好完整檔案後，再貼到 `nano`。若要刪除舊檔並重建，可使用：

    ```bash
    sudo rm -rf /etc/systemd/system/homepi-agent.service # 強制刪除舊檔
    sudo nano /etc/systemd/system/homepi-agent.service # 重建並一次性貼上
    ```

2.  **替換使用者名稱**：

    1. 原始檔在：[homepi-agent.service](../說明文件/systemd檔案/homepi-agent.service) 複製完整程式碼
    2. 將檔案中的 `qkauia` 替換成您在樹莓派上的使用者名稱。

    > [Service]區塊更改兩個部分：
    >
    > - `User=<你的使用者名稱>`
    > - `ExecStart=/usr/bin/python3 /home/<你的使用者名稱>/pi_agent/http_agent.py`

3.  **啟用與啟動服務**：
    **初次建立時**，請執行：

    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable homepi-agent.service
    sudo systemctl start homepi-agent.service
    ```

    **若只是修改服務檔**，則執行：

    ```bash
    sudo systemctl daemon-reload
    sudo systemctl restart homepi-agent.service
    ```

4.  **檢查服務狀態**：
    ```bash
    sudo systemctl status homepi-agent.service
    ```
    確認服務狀態為綠色的 `active (running)`，且沒有任何錯誤訊息。

---

##### 服務檔設定說明

```ini
[Unit]
# 說明服務用途，方便使用者識別。
Description=HomePi HTTP Agent
# 確保此服務在網路連線就緒後才啟動。
After=network-online.target
# 希望此服務在網路連線目標啟動時一起啟動。
Wants=network-online.target

[Service]
# 指定服務的啟動類型為 'simple'，表示主要程序由 ExecStart 執行。
Type=simple
# 指定執行此服務的使用者帳號，以確保執行權限正確。
User=qkauia
# 指定程式執行時的工作目錄。
WorkingDirectory=/home/qkauia/pi_agent

# ExecStart：主要的啟動命令，用於啟動您的 Python 程式。
ExecStart=/usr/bin/python3 /home/qkauia/pi_agent/http_agent.py
# Environment：設定環境變數，提供給程式使用。
# PYTHONUNBUFFERED=1：禁用 Python 緩衝，讓日誌輸出能即時顯示。
Environment=PYTHONUNBUFFERED=1
# GPIOZERO_PIN_FACTORY=lgpio：指定 GPIO 控制的 Pin Factory。
Environment=GPIOZERO_PIN_FACTORY=lgpio
# LED_PIN=17：設定 LED 燈的 GPIO 腳位。
Environment=LED_PIN=17
# LED_ACTIVE_HIGH=true：指定 LED 在高電位時為開啟狀態。
Environment=LED_ACTIVE_HIGH=true

# Restart：當服務因任何原因（例如錯誤）停止時，系統會自動重新啟動它。
Restart=always
# RestartSec：設定重啟前的等待時間為 3 秒。
RestartSec=3

[Install]
# 指定服務的啟用方式，當多用戶模式 (multi-user.target) 啟動時，此服務會被自動啟動。
WantedBy=multi-user.target
```

#### [上一步:03 樹梅派序號綁定](03樹梅派序號綁定.md)

#### [下一步:05 HLS 影片串流服務](<05HLS影片串流服務(homepi-hls.service).md>)
