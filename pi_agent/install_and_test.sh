#!/bin/bash
# 電子鎖安裝和測試腳本（樹莓派專用）

echo "🚀 電子鎖安裝和測試腳本"
echo "=================================================="

# 檢查是否在樹莓派上
if ! grep -q "BCM" /proc/cpuinfo; then
    echo "❌ 此腳本僅適用於樹莓派"
    exit 1
fi

echo "✅ 檢測到樹莓派硬體"

# 更新套件清單
echo "📦 更新套件清單..."
sudo apt update

# 安裝 Python 開發工具
echo "🔧 安裝 Python 開發工具..."
sudo apt install -y python3-dev python3-pip

# 安裝 gpiozero 和相關套件
echo "🔌 安裝 GPIO 相關套件..."
sudo apt install -y python3-gpiozero python3-rpi.gpio

# 安裝額外的 Python 套件
echo "📚 安裝 Python 套件..."
pip3 install --user gpiozero

# 檢查安裝狀態
echo "🔍 檢查安裝狀態..."
python3 -c "import gpiozero; print('✅ gpiozero 安裝成功')" || echo "❌ gpiozero 安裝失敗"

# 設定 GPIO 權限
echo "🔐 設定 GPIO 權限..."
sudo usermod -a -G gpio $USER
echo "⚠️  請重新登入以生效 GPIO 權限"

# 測試腳本
echo "🧪 開始測試..."
echo "=================================================="

# 執行快速測試
echo "🔧 執行快速硬體測試..."
python3 quick_test.py

echo ""
echo "🔧 執行完整測試..."
python3 test_locker.py

echo ""
echo "🎉 安裝和測試完成！"
echo ""
echo "💡 如果遇到權限問題，請執行："
echo "   sudo usermod -a -G gpio $USER"
echo "   然後重新登入"
echo ""
echo "💡 如果遇到腳位衝突，請檢查："
echo "   gpio readall"
echo "   確認沒有其他程式使用相同腳位"
