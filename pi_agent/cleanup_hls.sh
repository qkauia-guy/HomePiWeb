#!/bin/bash
# HLS 自動清理腳本
# 刪除超過 5MB 的異常 HLS 片段檔案

STREAM_DIR="/home/qkauia/pi_agent/stream"
MAX_SIZE="1M"

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
