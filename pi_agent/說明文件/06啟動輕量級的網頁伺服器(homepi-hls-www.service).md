<!-- markdownlint-disable -->

### homepi-hls-www.service：

這是一個 `systemd` 服務檔，它的主要功能是在您的樹莓派上啟動一個**輕量級的網頁伺服器**，用來提供 **HLS 影片串流的檔案**。

> 簡單來說，這個服務檔告訴樹莓派的系統：
>
> - **當網路就緒後**，且 **`homepi-hls.service` 服務已啟動後**，請執行這個服務。
> - **服務會啟動一個 Python 程式**，這個程式會：
>   - 以指定的使用者（`qkauia`）身份運行。
>   - 啟動一個網頁伺服器，將指定目錄中的影片檔案分享出來。
> - 如果程式因為任何原因停止，請**自動重新啟動**它，以確保串流服務不中斷。

---

##### 建立流程與注意事項

1.  **創建服務檔**：在終端機中，使用 `sudo nano` 指令來建立並編輯服務檔。

    ```bash
    sudo nano /etc/systemd/system/homepi-hls-www.service
    ```

    由於 `nano` 在處理多行程式碼時較難編輯，通常都建議在 `vscode` 中編輯好完整檔案後，再貼到 `nano`。若要刪除舊檔並重建，可使用：

    ```bash
    sudo rm -rf /etc/systemd/system/homepi-hls-www.service # 強制刪除舊檔
    sudo nano /etc/systemd/system/homepi-hls-www.service # 重建並一次性貼上
    ```

2.  **替換使用者名稱**：

    1. 複製完整程式碼。[homepi-hls-www.service](./systemd檔案/homepi-hls-www.service)
    2. 將檔案中的 `qkauia` 替換成您在樹莓派上的使用者名稱。

    > `[Service]` 區塊更改一個部分：
    >
    > - `User=<你的使用者名稱>`

3.  **啟用與啟動服務**：
    **初次建立時**，請執行：

    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable homepi-hls-www.service
    sudo systemctl start homepi-hls-www.service
    ```

    **若只是修改服務檔**，則執行：

    ```bash
    sudo systemctl daemon-reload
    sudo systemctl restart homepi-hls-www.service
    ```

4.  **檢查服務狀態**：
    ```bash
    sudo systemctl status homepi-hls-www.service
    ```
    確認服務狀態為綠色的 `active (running)`，且沒有任何錯誤訊息。

---

##### 服務檔設定說明

```ini
[Unit]
# 說明服務用途，方便使用者識別。
Description=HomePi HLS static web server (CORS) on :8088
# 確保此服務在網路連線就緒，且 homepi-hls.service 已啟動後才啟動。
After=network-online.target homepi-hls.service
# 希望此服務在網路連線目標啟動時一起啟動。
Wants=network-online.target

[Service]
# 指定服務的啟動類型為 'simple'，表示主要程序由 ExecStart 執行。
Type=simple
# 指定執行此服務的使用者帳號，以確保執行權限正確。
User=qkauia
# ExecStart：主要的啟動命令，用於啟動您的 Python 程式。
ExecStart=/usr/bin/python3 /home/qkauia/pi_agent/serve_hls.py
# Restart：當服務因任何原因（例如錯誤）停止時，系統會自動重新啟動它。
Restart=always
# RestartSec：設定重啟前的等待時間為 1 秒。
RestartSec=1

[Install]
# 指定服務的啟用方式，當多用戶模式 (multi-user.target) 啟動時，此服務會被自動啟動。
WantedBy=multi-user.target
```

#### [上一步:05 HLS 影片串流服務(homepi-hls.service)](<05HLS影片串流服務(homepi-hls.service).md>)
