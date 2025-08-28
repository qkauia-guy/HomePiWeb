<!-- markdownlint-disable -->

#### homepi-hls.service：

`homepi-hls.service` 是一個 `systemd` 服務檔，它的主要功能是讓您的 Raspberry Pi 在開機時自動啟動一個 HLS 影片串流服務。

> 簡單來說，這個服務檔告訴樹莓派的系統：
>
> - **當網路就緒後**，請執行這個服務。
> - **服務會啟動一個程式**，這個程式會：
>   - 使用相機模組錄影。
>   - 將錄影的畫面即時轉換成 HLS 串流格式（一種將影片分割成小片段的技術）。
>   - 將這些小影片片段儲存到指定的資料夾中。
> - 如果服務因為任何原因停止，請**自動重新啟動**它，以確保串流持續運行。

---

##### 建立流程與注意事項

1.  在終端機中，使用 `pwd` 確認您目前的目錄位於 `/home/你的user 目錄下`。

2.  **創建服務檔**
    `sudo nano /etc/systemd/system/homepi-hls.service`

    > 由於 `nano` 在處理多行程式碼時較難編輯，通常都建議在 `vscode` 中編輯好完整檔案後，再貼到 `nano`。若要刪除舊檔並重建，可使用：
    >
    > ```bash
    > sudo rm -rf /etc/systemd/system/homepi-hls.service # 強制刪除舊檔
    > sudo nano /etc/systemd/system/homepi-hls.service # 重建並一次性貼上
    > ```

3.  複製 [homepi-hls.service](./systemd檔案/homepi-hls.service) 中的乾淨程式碼，進行編輯。

4.  **重要：務必替換自己樹梅派的使用者名稱！**
    將檔案中所有 `qkauia` 替換成您在樹莓派上的使用者名稱。
    例如：

    - `User=<你的使用者名稱>`
    - `WorkingDirectory=/home/<你的使用者名稱>/pi_agent/stream`
    - `ExecStartPre=/usr/bin/bash -lc 'mkdir -p /home/<你的使用者名稱>/pi_agent/stream && rm -f /home/<你的使用者名稱>/pi_agent/stream/index.m3u8'`

5.  **注意：服務檔不能有備註！**
    在 `systemd` 的服務設定檔中，除了 `[Unit]`, `[Service]`, `[Install]` 等標頭，程式碼區塊內的註解（即 `#` 開頭的行）並不會被 systemd 解析，這可能會造成語法錯誤。

6.  樹莓派的 `路徑` 統一規格。

7.  **輸入 `systemctl` 指令以啟用服務：**

    **首次建立時**，請執行：

    ```bash
    # 重新載入 systemd 設定，讓系統知道有新的服務檔
    sudo systemctl daemon-reload
    # 啟用服務，讓它在開機時自動啟動
    sudo systemctl enable homepi-hls.service
    # 立即啟動服務
    sudo systemctl start homepi-hls.service
    ```

    **若只是修改已存在的服務檔**，則只需執行：

    ```bash
    # 重新載入設定檔的變更
    sudo systemctl daemon-reload
    # 重新啟動服務，讓變更生效
    sudo systemctl restart homepi-hls.service
    ```

8.  **檢查服務狀態**：

    ```bash
    sudo systemctl status homepi-hls.service
    ```

    確認是否沒有錯誤訊息，且服務正常運行。

9.  **參數可以自己調整測試**，以達到效能與延遲的最佳平衡。

---

##### 服務檔設定說明

```ini
[Unit]
# 說明服務用途，方便使用者識別。
Description=HomePi Camera HLS Stream (Low-Latency TS)
# 確保此服務在網路連線就緒後才啟動。
After=network-online.target
# 希望此服務在網路連線目標啟動時一起啟動。
Wants=network-online.target

[Service]
# 指定服務的啟動類型為 'simple'，表示主要程序由 ExecStart 執行。
Type=simple
# 指定執行此服務的使用者帳號，以確保執行權限正確。
User=qkauia
# 指定程式執行時的工作目錄，確保相對路徑下的檔案（如 stream）可以被找到。
WorkingDirectory=/home/qkauia/pi_agent/stream

# ExecStartPre：在主要命令 (ExecStart) 執行前，先執行此命令。
# 此命令會建立串流目錄（如果不存在），並刪除舊的 HLS 索引檔（index.m3u8）。
ExecStartPre=/usr/bin/bash -lc 'mkdir -p /home/qkauia/pi_agent/stream && rm -f /home/qkauia/pi_agent/stream/index.m3u8'

# ExecStart：主要的啟動命令。這裡使用多行命令和管道 (pipe) 來連接兩個程式。
# 'bash -lc' 用來確保命令在一個完整且正確的環境中執行。
ExecStart=/usr/bin/bash -lc '\
# rpicam-vid：Raspberry Pi 相機軟體，用於擷取影片。
# -t 0：將錄影時間設為無限。
/usr/bin/rpicam-vid -t 0 \
# --width 1280 --height 720：設定影片解析度為 720p。
  --width 1280 --height 720 --framerate 30 \
# --framerate 30：設定每秒影格數為 30。
# --codec h264：指定影片編碼格式為 H.264。
  --codec h264 --profile baseline --level 4.0 \
# --intra 15：設定關鍵影格 (I-frame) 的間隔為 15 個影格。這有助於降低延遲。
# --inline：確保所有關鍵影格都包含所有必要的解碼資訊。
  --intra 15 --inline --nopreview \
# --nopreview：禁用預覽視窗。
# --libav-format h264 -o -：將 H.264 格式的影片輸出到標準輸出（stdout）。
  --libav-format h264 -o - \
# |：管道符號，將 rpicam-vid 的輸出導向 ffmpeg 的輸入。
| \
# ffmpeg：開源多媒體工具，用於將影片轉碼為 HLS 格式。
# -loglevel warning：只顯示警告以上的日誌訊息，減少輸出內容。
  /usr/bin/ffmpeg -loglevel warning -fflags +genpts -use_wallclock_as_timestamps 1 \
# -f h264 -i -：將輸入格式設為 H.264，並從標準輸入（stdin）讀取。
  -f h264 -i - -c:v copy -an \
# -c:v copy：直接複製影片編碼，不重新編碼以節省 CPU 資源。
# -an：禁用音訊串流。
# -f hls：指定輸出格式為 HLS。
  -f hls -hls_time 0.5 -hls_list_size 3 -start_number 1 \
# -hls_time 0.5：設定每個影片片段 (.ts) 的長度為 0.5 秒，是實現低延遲的關鍵。
# -hls_list_size 3：設定 HLS 清單 (.m3u8) 中保留的影片片段數量為 3。
# -start_number 1：從編號 1 開始命名影片片段。
# -hls_flags delete_segments+append_list...：指定 HLS 相關的進階選項。
# delete_segments：自動刪除舊的影片片段，以節省空間。
  -hls_flags delete_segments+append_list+program_date_time+independent_segments+temp_file \
# -hls_segment_filename：指定影片片段 (.ts) 的檔名格式。
# %%05d：`%%` 是跳脫字元，代表一個 `%`，`05d` 則代表 5 位數的編號，例如 seg_00001.ts。
  -hls_segment_filename /home/qkauia/pi_agent/stream/seg_%%05d.ts \
# 最後一個參數是 HLS 清單 (.m3u8) 的輸出路徑和檔名。
  /home/qkauia/pi_agent/stream/index.m3u8 \
'

# Restart：當服務因任何原因（例如錯誤）停止時，系統會自動重新啟動它。
Restart=always
# RestartSec：設定重啟前的等待時間為 2 秒。
RestartSec=2

[Install]
# 指定服務的啟用方式，當多用戶模式 (multi-user.target) 啟動時，此服務會被自動啟動。
WantedBy=multi-user.target
```

#### [上一步:04 HTTP 代理程式(homepi-http-agent.service)](<04HTTP代理程式(homepi-http-agent.service).md>)

#### [06 啟動輕量級的網頁伺服器(homepi-hls-www.service)](<06啟動輕量級的網頁伺服器(homepi-hls-www.service).md>)
