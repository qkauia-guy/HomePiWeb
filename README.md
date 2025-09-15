# HomePi Web - 樹莓派物聯網管理系統

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.2+-green.svg)](https://djangoproject.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📋 專案概述

HomePi Web 是一個基於 Django 的樹莓派物聯網管理系統，提供完整的裝置管理、群組分享、邀請制度、通知系統等功能。支援多種 IoT 裝置控制，包括燈光、風扇、電子鎖等，並具備即時串流和排程功能。

## ✨ 主要功能

### 🏠 裝置管理

- **多裝置支援**: 支援多台樹莓派裝置同時管理
- **即時狀態監控**: 裝置線上/離線狀態即時顯示
- **QR Code 綁定**: 透過 QR Code 快速綁定新裝置
- **裝置能力管理**: 動態配置裝置功能（燈光、風扇、電子鎖等）

### 👥 群組與權限

- **群組管理**: 建立群組並分享裝置給其他使用者
- **角色權限**: 支援 Admin、Operator、Viewer 三種角色
- **裝置分享**: 靈活的裝置分享申請與審核機制
- **權限控制**: 細粒度的裝置操作權限管理

### 🔐 電子鎖功能

- **遠端控制**: 支援遠端上鎖、開鎖、切換操作
- **自動上鎖**: 開鎖後自動計時上鎖功能
- **狀態指示**: 雙 LED 狀態指示（綠燈=開鎖，紅燈=上鎖）
- **手動操作**: 支援按鈕手動操作與遠端控制同步

### 📹 即時串流

- **HLS 串流**: 支援即時視訊串流功能
- **代理服務**: 內建 HLS 代理服務，支援跨域存取
- **串流狀態**: 即時顯示串流狀態和 URL

### 📅 排程系統

- **定時任務**: 支援裝置定時開關控制
- **自動化**: 自動感光控制（BH1750 感測器 → LED）
- **任務管理**: 完整的排程任務生命週期管理

### 🔔 通知系統

- **即時通知**: 系統事件即時通知
- **通知分類**: 支援成員、裝置等多種通知類型
- **已讀管理**: 通知已讀/未讀狀態管理

## 🏗️ 系統架構

### 後端技術棧

- **框架**: Django 5.2+
- **資料庫**: PostgreSQL (開發環境支援 SQLite)
- **API**: Django REST Framework
- **快取**: MongoDB (日誌儲存)
- **虛擬環境**: Conda

### 前端技術棧

- **UI 框架**: Bootstrap 5
- **JavaScript**: 原生 ES6+ (模組化設計)
- **圖表**: Chart.js
- **通知**: SweetAlert2
- **即時更新**: AJAX 輪詢機制

### 樹莓派端

- **代理程式**: HTTP Agent (長輪詢通訊)
- **硬體控制**: RPi.GPIO, 伺服馬達控制
- **串流服務**: rpicam-vid + ffmpeg
- **感測器**: BH1750 光感測器
- **服務管理**: systemd 服務

## 📦 安裝與設定

### 環境需求

- Python 3.11+
- PostgreSQL 12+ (或 SQLite 用於開發)
- MongoDB (可選，用於日誌)
- Conda 虛擬環境管理

### 1. 克隆專案

```bash
git clone <repository-url>
cd HomePiWeb
```

### 2. 建立虛擬環境

```bash
# 使用 Conda 建立環境
conda create --name HomePiWeb python=3.11
conda activate HomePiWeb

# 或使用 venv
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate  # Windows
```

### 3. 安裝依賴

```bash
pip install -r requirements.txt
```

### 4. 環境設定

```bash
# 複製環境變數範本
cp .env.example .env

# 編輯環境變數
nano .env
```

### 5. 資料庫設定

```bash
# 執行資料庫遷移
python manage.py migrate

# 建立超級使用者
python manage.py createsuperuser
```

### 6. 啟動開發伺服器

```bash
python manage.py runserver 0.0.0.0:8800
```

## 🔧 樹莓派設定

### 1. 安裝依賴

```bash
# 安裝 Python 依賴
pip install -r pi_agent/requirements.txt

# 安裝系統依賴
sudo apt update
sudo apt install -y python3-rpi.gpio python3-pip
```

### 2. 硬體接線

```yaml
# 電子鎖接線範例
電子鎖:
  按鈕: GPIO 27
  伺服馬達: GPIO 18
  綠燈 (開鎖): GPIO 23
  紅燈 (上鎖): GPIO 22

# 光感測器
BH1750:
  SDA: GPIO 2
  SCL: GPIO 3
```

### 3. 設定檔案

```yaml
# pi_agent/config/homepi.yml
server:
  url: 'http://your-server:8800'
  token: 'your-device-token'

devices:
  - name: 'main_light'
    kind: 'light'
    config:
      pin: 18
  - name: 'main_locker'
    kind: 'locker'
    config:
      button_pin: 27
      servo_pin: 18
      led_green: 23
      led_red: 22
      auto_lock_delay: 10
```

### 4. 啟動服務

```bash
# 啟動 HTTP Agent
sudo systemctl start homepi-http-agent@your-device-id

# 啟動 HLS 串流
sudo systemctl start homepi-hls@your-device-id

# 啟動排程服務
sudo systemctl start homepi-scheduler@your-device-id
```

## 📱 使用指南

### 1. 裝置綁定

1. 在樹莓派上啟動 HTTP Agent
2. 掃描 QR Code 或輸入驗證碼
3. 設定裝置顯示名稱
4. 配置裝置能力

### 2. 群組管理

1. 建立群組並設定名稱
2. 邀請成員加入群組
3. 將裝置分享到群組
4. 設定成員權限

### 3. 裝置控制

1. 選擇群組和裝置
2. 選擇要控制的功能
3. 使用控制按鈕操作
4. 查看即時狀態更新

### 4. 電子鎖操作

1. 選擇包含電子鎖的裝置
2. 使用上鎖/開鎖/切換按鈕
3. 監控自動上鎖狀態
4. 查看 LED 狀態指示

## 🔌 API 文件

### 裝置通訊 API

```http
# 裝置心跳
POST /api/device/ping/
Content-Type: application/json
{
  "serial": "PI-XXXXXXXX",
  "token": "device-token",
  "status": "online"
}

# 拉取指令
POST /api/device/pull/
Content-Type: application/json
{
  "serial": "PI-XXXXXXXX",
  "token": "device-token"
}

# 回報執行結果
POST /api/device/ack/
Content-Type: application/json
{
  "serial": "PI-XXXXXXXX",
  "req_id": "command-request-id",
  "status": "done",
  "result": {...}
}
```

### 裝置控制 API

```http
# 相機控制
POST /api/camera/{serial}/{action}/
{
  "action": "start|stop|status"
}

# 能力控制
POST /api/capability/{serial}/{cap_slug}/{action}/
{
  "action": "light_on|light_off|locker_lock|locker_unlock"
}
```

## 📊 資料庫結構

### 主要模型

- **User**: 使用者管理 (email 登入)
- **Device**: 樹莓派裝置
- **DeviceCapability**: 裝置功能配置
- **Group**: 群組管理
- **GroupMembership**: 群組成員關係
- **DeviceCommand**: 裝置指令佇列
- **DeviceSchedule**: 排程任務
- **Notification**: 通知系統

### 關聯關係

```
User (1:N) Device
User (M:N) Group (through GroupMembership)
Device (1:N) DeviceCapability
Device (1:N) DeviceCommand
Device (1:N) DeviceSchedule
Group (M:N) Device (through GroupDevice)
```

## 🚀 部署指南

### 生產環境設定

```python
# settings.py
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com']
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'homepi_prod',
        'USER': 'homepi_user',
        'PASSWORD': 'secure_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### Nginx 設定

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8800;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static/ {
        alias /path/to/HomePiWeb/static/;
    }

    location /media/ {
        alias /path/to/HomePiWeb/media/;
    }
}
```

### systemd 服務

```ini
# /etc/systemd/system/homepi.service
[Unit]
Description=HomePi Web Application
After=network.target

[Service]
Type=exec
User=homepi
Group=homepi
WorkingDirectory=/path/to/HomePiWeb
Environment=PATH=/path/to/HomePiWeb/venv/bin
ExecStart=/path/to/HomePiWeb/venv/bin/gunicorn HomePiWeb.wsgi:application
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
```

## 🧪 測試

### 執行測試

```bash
# 執行所有測試
python manage.py test

# 執行特定 app 測試
python manage.py test users
python manage.py test pi_devices
python manage.py test groups
```

### 測試覆蓋率

```bash
# 安裝 coverage
pip install coverage

# 執行測試並產生報告
coverage run --source='.' manage.py test
coverage report
coverage html
```

## 📝 開發指南

### 程式碼風格

- 遵循 PEP8 規範
- 使用 Black 自動格式化
- 使用 isort 自動排序 import
- 程式碼註解使用正體繁體中文

### Git 工作流程

- 使用 Conventional Commits 格式
- 功能分支開發
- Pull Request 審查
- 自動化測試檢查

### 新增裝置功能

1. 在 `DeviceCapability.KIND_CHOICES` 新增功能類型
2. 建立對應的硬體控制模組
3. 實作前端控制介面
4. 新增 JavaScript 控制邏輯
5. 更新 API 端點

## 🐛 常見問題

### Q: 裝置無法連線？

A: 檢查網路連線、防火牆設定、HTTP Agent 服務狀態

### Q: 電子鎖無法控制？

A: 確認 GPIO 接線正確、權限設定、硬體驅動安裝

### Q: 串流無法播放？

A: 檢查 rpicam-vid 安裝、HLS 服務狀態、網路頻寬

### Q: 通知不顯示？

A: 確認通知服務啟動、資料庫連線、前端 JavaScript 載入

## 📄 授權

本專案採用 MIT 授權條款。詳見 [LICENSE](LICENSE) 檔案。

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

1. Fork 本專案
2. 建立功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交變更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

## 📞 支援

如有問題或建議，請透過以下方式聯繫：

- 提交 [Issue](https://github.com/your-repo/issues)
- 發送 Email: kauia96@example.com

---

**HomePi Web** - 讓樹莓派物聯網管理變得簡單易用 🏠✨
