# HLS 自動清理腳本設定指南

## 概述

本指南說明如何在樹莓派上設定 HLS 自動清理腳本，防止直播視訊檔案佔滿磁碟空間。

## 問題背景

HLS (HTTP Live Streaming) 直播服務有時會產生異常大的視訊片段檔案（正常應該只有幾百 KB，但可能變成幾百 MB），導致樹莓派磁碟空間不足。雖然 FFmpeg 有 `delete_segments` 標誌，但在某些情況下會失效。

## 解決方案

建立自動清理腳本，定期檢查並刪除異常大的 HLS 片段檔案。

---

## 設定步驟

### 1. 建立清理腳本

在樹莓派上執行以下命令：

```bash
# 切換到 pi_agent 目錄
cd /home/你的使用者名稱/pi_agent

# 建立清理腳本
cat > cleanup_hls.sh << 'EOF'
#!/bin/bash
# HLS 自動清理腳本
# 刪除超過 5MB 的異常 HLS 片段檔案

STREAM_DIR="/home/你的使用者名稱/pi_agent/stream"
MAX_SIZE="5M"

echo "$(date): 開始清理 HLS 檔案..."

# 找出超過 5MB 的 .ts 檔案
LARGE_FILES=$(find "$STREAM_DIR" -name "seg_*.ts" -size +$MAX_SIZE -type f)

if [ -n "$LARGE_FILES" ]; then
    echo "發現異常大的檔案："
    echo "$LARGE_FILES"
    
    # 刪除這些檔案
    echo "$LARGE_FILES" | xargs rm -f
    echo "已刪除異常大的 HLS 片段檔案"
else
    echo "沒有發現異常大的檔案"
fi

# 顯示目前 stream 目錄大小
CURRENT_SIZE=$(du -sh "$STREAM_DIR" | cut -f1)
echo "目前 stream 目錄大小: $CURRENT_SIZE"

echo "$(date): HLS 清理完成"
EOF
```

**重要：請將腳本中的 `你的使用者名稱` 替換為實際的使用者名稱！**

### 2. 設定腳本權限

```bash
chmod +x cleanup_hls.sh
```

### 3. 測試腳本

```bash
# 手動執行一次測試
./cleanup_hls.sh
```

### 4. 設定自動執行

使用 crontab 設定每 10 分鐘自動執行：

```bash
# 設定定時任務（每 10 分鐘執行一次）
echo "*/10 * * * * /home/你的使用者名稱/pi_agent/cleanup_hls.sh >> /home/你的使用者名稱/pi_agent/cleanup.log 2>&1" | crontab -
```

**重要：請將命令中的 `你的使用者名稱` 替換為實際的使用者名稱！**

### 5. 驗證設定

```bash
# 檢查 crontab 設定
crontab -l

# 檢查腳本檔案
ls -la cleanup_hls.sh

# 檢查日誌檔案（執行後會產生）
ls -la cleanup.log
```

---

## 使用說明

### 手動執行

```bash
# 手動執行清理腳本
./cleanup_hls.sh

# 或使用完整路徑
bash /home/你的使用者名稱/pi_agent/cleanup_hls.sh
```

### 查看執行記錄

```bash
# 查看清理日誌
cat cleanup.log

# 即時監控日誌
tail -f cleanup.log
```

### 檢查磁碟使用情況

```bash
# 檢查整體磁碟使用
df -h

# 檢查 stream 目錄大小
du -sh stream/
```

---

## 進階設定

### 調整清理頻率

如果需要調整清理頻率，可以修改 crontab：

```bash
# 編輯 crontab
crontab -e

# 常見設定：
# 每 5 分鐘：*/5 * * * *
# 每 15 分鐘：*/15 * * * *
# 每小時：0 * * * *
# 每天凌晨 2 點：0 2 * * *
```

### 調整檔案大小閾值

如果需要調整檔案大小閾值，編輯腳本中的 `MAX_SIZE` 變數：

```bash
# 編輯腳本
nano cleanup_hls.sh

# 修改這一行：
MAX_SIZE="10M"  # 改為 10MB
```

### 停止自動清理

```bash
# 移除 crontab 設定
crontab -r
```

---

## 故障排除

### 腳本無法執行

1. 檢查檔案權限：
   ```bash
   ls -la cleanup_hls.sh
   # 應該顯示 -rwxr-xr-x
   ```

2. 檢查路徑是否正確：
   ```bash
   pwd
   # 確認在正確的目錄
   ```

### crontab 沒有執行

1. 檢查 crontab 服務狀態：
   ```bash
   sudo systemctl status cron
   ```

2. 檢查 crontab 設定：
   ```bash
   crontab -l
   ```

3. 檢查系統日誌：
   ```bash
   sudo journalctl -u cron -n 20
   ```

### 權限問題

如果遇到權限問題，確保腳本有執行權限：

```bash
chmod +x cleanup_hls.sh
```

---

## 注意事項

1. **備份重要資料**：清理腳本會刪除檔案，請確保沒有重要資料在 stream 目錄中
2. **監控日誌**：定期檢查 `cleanup.log` 確認腳本正常執行
3. **調整參數**：根據實際需求調整清理頻率和檔案大小閾值
4. **使用者名稱**：務必將腳本中的 `你的使用者名稱` 替換為實際的使用者名稱

---

## 相關檔案

- `cleanup_hls.sh` - 清理腳本
- `cleanup.log` - 執行日誌
- `stream/` - HLS 檔案目錄

---

## 支援

如果遇到問題，請檢查：
1. 腳本權限是否正確
2. 路徑是否正確
3. crontab 設定是否正確
4. 系統日誌是否有錯誤訊息
