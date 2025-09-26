HomePi 服務啟動與確認流程 (Markdown 版)
以下為 完整 Markdown 原始檔，用於在 Raspberry Pi 上檢查、啟動與確認 homepi-\* 系列服務的流程。Instance 名稱固定為 @qkauia。
**_1. 檢查服務檔案是否存在
systemctl list-unit-files | grep homepi
確認有哪些 homepi-_ 單元檔（unit files）。
可能的狀態：enabled、disabled、static、indirect。 \***2. 檢查目前的執行狀態
systemctl list-units --all | grep homepi
查看 active / inactive / failed 狀態。
--all 會包含已停止或失敗的單元。
**_3. 檢查是否有殘留的行程
ps aux | grep homepi
pgrep -a rpicam-vid
pgrep -a ffmpeg
確認是否有未被 systemd 管理的殘留程式（例如手動啟動的 rpicam-vid 或 ffmpeg）。
_**4. 啟動主要服務（@qkauia）
立即啟動
sudo systemctl start homepi-agent@qkauia.service
sudo systemctl start homepi-hls@qkauia.service
sudo systemctl start homepi-hls-www@qkauia.service
sudo systemctl start homepi-scheduler@qkauia.service
立即重啟動
sudo systemctl restart homepi-agent@qkauia.service
sudo systemctl restart homepi-hls@qkauia.service
sudo systemctl restart homepi-hls-www@qkauia.service
sudo systemctl restart homepi-scheduler@qkauia.service
設定開機自動啟動
sudo systemctl enable homepi-agent@qkauia.service
sudo systemctl enable homepi-hls@qkauia.service
sudo systemctl enable homepi-hls-www@qkauia.service
sudo systemctl enable homepi-scheduler@qkauia.service

> 若需要暫停，使用 sudo systemctl stop <unit>；若需重新載入設定，用 sudo systemctl daemon-reload 後再 restart。
> **_5. 檢查服務狀態
> systemctl status homepi-agent@qkauia.service
> systemctl status homepi-hls@qkauia.service
> systemctl status homepi-hls-www@qkauia.service
> systemctl status homepi-scheduler@qkauia.service
> _**6. 查看詳細錯誤日誌
> 當服務啟動失敗（failed）時，請查看日誌：
> journalctl -u homepi-hls@qkauia.service -n 50 --no-pager
> 將 homepi-hls@qkauia.service 替換為你要排查的單元名稱。
> -n 50 顯示最近 50 行，可依需要調整。
> \*\*\*✅ 依照以上流程，可以完整確認、啟動並檢查 HomePi 相關服務的運行狀態。
