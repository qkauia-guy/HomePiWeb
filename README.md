## HomePiWeb 專案說明

HomePiWeb 是一個以 Django 為核心、搭配樹梅派 (Raspberry Pi) 代理程式的家庭裝置管理平台。後端提供群組/裝置/邀請/通知等功能，前端以 Django Templates 搭配靜態資源運作，樹梅派端則由 `pi_agent` 進行裝置偵測、控制與串流。

### 功能總覽

- 群組與分享權限管理（`groups/`）
- 裝置與能力管理、API 服務（`pi_devices/`）
- 邀請碼與裝置分享（`invites/`）
- 通知中心與事件（`notifications/`）
- 樹梅派 Agent：感測器/相機/電子鎖/排程/HLS 串流（`pi_agent/`）

### 專案結構（精要）

```
HomePiWeb/
  HomePiWeb/            # Django 專案設定
  groups/               # 群組與分享權限
  invites/              # 邀請/分享
  notifications/        # 通知與服務
  pi_devices/           # 裝置與 API
  users/                # 使用者相關
  pi_agent/             # 樹梅派端代理程式
  templates/            # Django Templates
  static/               # 前端靜態資源
  media/                # 上傳/串流媒體
  manage.py             # Django 管理指令
  environment.yml       # Conda 環境（macOS/Raspberry Pi）
```

---

## 開發環境安裝（macOS 與 Raspberry Pi 通用）

本專案使用 Conda 建立隔離環境，Python 版本以 3.x 最新穩定版為主。

### 1. 安裝 Conda（建議使用 Miniconda 或 Mambaforge）

可參考官方文件安裝，或使用下列指令（以 macOS ARM 為例，請依你的平台調整）：

```bash
# 例：使用 Homebrew 安裝 micromamba（啟動快、效能佳）
brew install micromamba
```

### 2. 建立並啟用環境

```bash
cd /Users/qkauia/Desktop/HomePiWeb
micromamba create -y -n homepi -f environment.yml
micromamba activate homepi
```

若你使用 conda：

```bash
conda env create -n homepi -f environment.yml
conda activate homepi
```

### 3. 初始化資料庫與管理者帳號

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 4. 啟動開發伺服器

```bash
python manage.py runserver 0.0.0.0:8800
```

瀏覽器開啟 `http://localhost:8800/`，或以區網 IP 存取。

---

## 前端與靜態資源

### 技術架構

- **模板引擎**：Django Templates
- **CSS 框架**：Bootstrap 5.3.3 + 自訂 CSS
- **JavaScript**：原生 ES6+ JavaScript（模組化設計）
- **圖表庫**：Chart.js
- **通知系統**：SweetAlert2
- **圖示**：Bootstrap Icons

### 目錄結構

```
static/home_pi_web/
├── css/
│   ├── base.css          # 基礎樣式、主題切換、響應式設計
│   ├── home.css          # 首頁專用樣式
│   └── groups/           # 群組相關樣式
├── js/
│   ├── base.js           # 基礎功能、主題切換
│   ├── SweetAlert2.js    # 通知系統
│   ├── home/             # 首頁功能模組
│   │   ├── home.init.js      # 初始化
│   │   ├── home.controls.js  # 設備控制
│   │   ├── home.polling.js   # 狀態輪詢
│   │   ├── home.chart.js     # 圖表功能
│   │   ├── home.mobile.js    # 手機版適配
│   │   └── ...
│   ├── groups/           # 群組功能
│   └── users/            # 使用者功能
└── images/               # 靜態圖片資源

templates/
├── base.html             # 基礎模板
├── home/                 # 首頁模板
├── groups/               # 群組模板
├── users/                # 使用者模板
└── pi_devices/           # 設備模板
```

### 主要功能模組

#### 1. 主題系統

- **黑夜/白天模式**：自動偵測系統偏好，支援手動切換
- **響應式設計**：桌面版和手機版適配
- **毛玻璃效果**：現代化 UI 設計

#### 2. 設備控制

- **即時控制**：LED 開關、電子鎖控制
- **狀態監控**：設備線上狀態、心跳檢測
- **圖表展示**：設備使用統計、效能監控

#### 3. 群組管理

- **動態載入**：AJAX 群組和設備選擇
- **權限控制**：基於角色的功能顯示
- **邀請系統**：QR Code 分享、權限設定

#### 4. 通知系統

- **SweetAlert2 整合**：美觀的彈窗通知
- **主題適配**：自動適應黑夜/白天模式
- **訊息分類**：成功、警告、錯誤訊息

### 開發指南

#### 新增頁面樣式

```css
/* 在 static/home_pi_web/css/ 中新增樣式檔案 */
/* 遵循現有的 CSS 變數和命名規範 */
.custom-component {
  background: var(--bg-primary);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}
```

#### 新增 JavaScript 功能

```javascript
// 在 static/home_pi_web/js/ 中新增模組
// 遵循現有的模組化設計
(function () {
  'use strict';

  // 模組功能實作
  function initCustomFeature() {
    // 功能邏輯
  }

  // 初始化
  document.addEventListener('DOMContentLoaded', initCustomFeature);
})();
```

#### 模板開發

```html
<!-- 在 templates/ 中新增模板 -->
<!-- 繼承 base.html 並使用現有的 CSS 類別 -->
{% extends "base.html" %} {% load static %} {% block extra_head %}
<link
  rel="stylesheet"
  href="{% static 'home_pi_web/css/custom.css' %}" />
{% endblock %} {% block content %}
<div class="container">
  <!-- 使用 Bootstrap 和自訂 CSS 類別 -->
  <div class="glass-card">
    <div class="card-body">
      <!-- 內容 -->
    </div>
  </div>
</div>
{% endblock %}
```

### 生產環境部署

```bash
# 收集靜態檔案
python manage.py collectstatic --noinput

# 設定靜態檔案服務（Nginx 範例）
location /static/ {
    alias /path/to/static/;
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### 效能優化

- **CSS/JS 壓縮**：使用 `collectstatic` 收集並壓縮
- **圖片優化**：使用適當的圖片格式和尺寸
- **快取策略**：設定適當的 HTTP 快取標頭
- **CDN 整合**：Bootstrap 和圖示使用 CDN 載入

---

## 樹梅派 Agent（pi_agent）

`pi_agent/` 提供裝置偵測、HTTP 代理、HLS 串流與排程等服務，設定檔位於 `pi_agent/config/homepi.yml`。

### 1. 樹梅派環境準備

#### 安裝必要套件

```bash
# 系統套件
sudo apt-get install -y python3-gpiozero python3-lgpio python3-smbus python3-libgpiod i2c-tools
sudo apt install nginx -y
sudo apt update && sudo apt install -y pigpio

# Python 套件
pip3 install smbus2 pyyaml python-dotenv adafruit-circuitpython-dht psutil
```

#### 設定 GPIO 權限

```bash
# 加入必要群組
sudo adduser $USER dialout
sudo adduser $USER gpio

# 設定目錄權限
sudo chown -R $USER:$USER /home/$USER/pi_agent
```

#### 安裝 Conda 環境

```bash
# 下載 Miniforge (64-bit ARM 版本，適用 Raspberry Pi 4/5)
wget https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-aarch64.sh
chmod +x Miniforge3-Linux-aarch64.sh
./Miniforge3-Linux-aarch64.sh

# 啟用 Conda
source ~/miniforge3/etc/profile.d/conda.sh

# 建立環境
conda create -n HomePiWeb python=3.11 -y
conda activate HomePiWeb
```

### 2. 專案部署

#### 同步專案到樹梅派

```bash
# 方法一：使用 rsync（推薦）
rsync -avz /path/to/HomePiWeb/pi_agent/ <樹梅派IP>:/home/<username>/pi_agent/

# 方法二：使用 robocopy（Windows）
robocopy C:\path\to\HomePiWeb\pi_agent \\<樹梅派IP>\pi_agent /MIR
```

#### 設定環境變數

```bash
cd /home/$USER/pi_agent
nano .env
```

在 `.env` 檔案中設定：

```
SERIAL_NUMBER=PI-XXXXXXXX
TOKEN=your_device_token
SERVER_URL=http://your-server-ip:8800
```

### 3. 設備序號綁定

#### 在本地專案建立設備

```bash
python manage.py shell
```

```python
from pi_devices.models import Device
from pi_devices.utils.qrcode_utils import generate_device_qrcode

# 建立新設備
device = Device.objects.create()
print(f"序號: {device.serial_number}")
print(f"Token: {device.token}")
print(f"驗證碼: {device.verification_code}")

# 產生 QR Code
file_path = generate_device_qrcode(device)
print(f"QR Code 已儲存於: {file_path}")
```

#### 掃描 QR Code 綁定

1. 掃描產生的 QR Code
2. 導向註冊頁面，系統會自動填入序號和驗證碼
3. 完成註冊後設備會自動綁定

### 4. 啟動服務

#### 測試執行

```bash
# 啟動 HTTP 代理（測試）
python pi_agent/http_agent.py

# 啟動 HLS 串流（測試）
python pi_agent/serve_hls.py
```

#### 設定 systemd 服務（生產環境）

專案內含服務範本（`pi_agent/說明文件/systemd檔案/`）：

- `homepi-http-agent@.service` - HTTP 代理服務
- `homepi-hls@.service` - HLS 串流服務
- `homepi-hls-www@.service` - 輕量級網頁伺服器
- `homepi-scheduler@.service` - 排程服務

安裝步驟：

```bash
# 複製服務檔案
sudo cp pi_agent/說明文件/systemd檔案/*.service /etc/systemd/system/

# 重新載入 systemd
sudo systemctl daemon-reload

# 啟用並啟動服務
sudo systemctl enable homepi-http-agent@$USER.service
sudo systemctl enable homepi-hls@$USER.service
sudo systemctl enable homepi-scheduler@$USER.service

sudo systemctl start homepi-http-agent@$USER.service
sudo systemctl start homepi-hls@$USER.service
sudo systemctl start homepi-scheduler@$USER.service

# 檢查服務狀態
sudo systemctl status homepi-http-agent@$USER.service
```

### 5. 進階設定

#### HLS 自動清理腳本

```bash
# 建立清理腳本
cat > cleanup_hls.sh << 'EOF'
#!/bin/bash
STREAM_DIR="/home/$USER/pi_agent/stream"
MAX_SIZE="5M"

echo "$(date): 開始清理 HLS 檔案..."
LARGE_FILES=$(find "$STREAM_DIR" -name "seg_*.ts" -size +$MAX_SIZE -type f)

if [ -n "$LARGE_FILES" ]; then
    echo "$LARGE_FILES" | xargs rm -f
    echo "已刪除異常大的 HLS 片段檔案"
fi

echo "$(date): HLS 清理完成"
EOF

chmod +x cleanup_hls.sh

# 設定自動執行（每 10 分鐘）
echo "*/10 * * * * /home/$USER/pi_agent/cleanup_hls.sh >> /home/$USER/pi_agent/cleanup.log 2>&1" | crontab -
```

#### 詳細設定指南

更多詳細設定請參考 `pi_agent/說明文件/` 目錄下的文件：

- [01 本地環境設定.md](pi_agent/說明文件/01本地環境設定.md) - 本地開發環境設定
- [02 樹梅派環境設定.md](pi_agent/說明文件/02樹梅派環境設定.md) - 樹梅派環境完整設定
- [03 樹梅派序號綁定.md](pi_agent/說明文件/03樹梅派序號綁定.md) - 設備序號綁定流程
- [04HTTP 代理程式(homepi-http-agent@.service).md](<pi_agent/說明文件/04HTTP代理程式(homepi-http-agent@.service).md>) - HTTP 代理服務設定
- [05HLS 影片串流服務(homepi-hls@.service).md](<pi_agent/說明文件/05HLS影片串流服務(homepi-hls@.service).md>) - HLS 串流服務設定
- [06 啟動輕量級的網頁伺服器(homepi-hls-www@.service).md](<pi_agent/說明文件/06啟動輕量級的網頁伺服器(homepi-hls-www@.service).md>) - 網頁伺服器設定
- [07 排程服務(homepi-scheduler@.service).md](<pi_agent/說明文件/07排程服務(homepi-scheduler@.service).md>) - 排程服務設定
- [08 多台裝置同步誤動作排查.md](pi_agent/說明文件/08多台裝置同步誤動作排查.md) - 故障排除指南
- [HLS 自動清理腳本設定指南.md](pi_agent/說明文件/HLS自動清理腳本設定指南.md) - HLS 檔案自動清理設定
- [快速設定腳本.md](pi_agent/說明文件/快速設定腳本.md) - 快速部署腳本
- [pi 裝置擴充設定說明.md](pi_agent/說明文件/pi裝置擴充設定說明.md) - 裝置功能擴充指南
- [樹梅派專案結構\_詳細註解.md](pi_agent/說明文件/樹梅派專案結構_詳細註解.md) - 專案結構詳細說明

---

## 環境設定建議

在 `HomePiWeb/settings.py` 中設定：

```python
DEBUG = True  # 開發環境建議開啟，生產請關閉
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "::1", "你的伺服器IP或網域"]
```

生產環境建議使用環境變數或 `.env` 檔管理敏感資訊（如 SECRET_KEY、資料庫連線）。

---

## 資料庫操作

```bash
# 建立遷移檔
python manage.py makemigrations

# 套用遷移
python manage.py migrate
```

備註：專案提供部分管理指令於 `pi_devices/management/commands/`。

---

## 測試

```bash
python manage.py test
```

測試以 Django 測試框架執行，Python 語法以 3.x 新語法為主，並遵循 PEP8；請使用 Black 與 isort 進行格式化與 import 排序。

---

## 簡易 API 範例（示意）

以下為示意範例，實際端點以 `HomePiWeb/urls.py` 與各 app `urls.py`/`views.py` 為準。

```bash
# 取得通知列表（若有提供對外 API）
curl -H "Authorization: Token <YOUR_TOKEN>" \
  http://localhost:8800/notifications/api/list

# 取得裝置列表/能力（視專案 API 設計）
curl -H "Authorization: Token <YOUR_TOKEN>" \
  http://localhost:8800/pi-devices/api/devices
```

---

## 研發流程與提交規範

- Commit 規範採用 Conventional Commits：
  - `feat: 新功能`
  - `fix: 修正問題`
  - `docs: 文件更新`
  - 其餘可依照標準延伸（如 `refactor:`, `test:`, `chore:`）

---

## 常見問題與故障排除

- Wi-Fi/網路不穩：參考 `解決wifi浮動辦法們.md`
- 樹梅派功能與環境設定：參考 `pi_agent/說明文件/` 內各章節
- 專案結構與說明：`專案資料結構文件.md`

---

## 設備開通與綁定流程（QR 綁定）

以下為設備出廠到使用者綁定的標準流程：

1. **設備出廠**

   - 樹梅派具唯一設備序號（格式：`PI-XXXXXXXX`）、驗證碼與 QR Code
   - QR Code 包含註冊 URL：`http://[伺服器IP]:8800/register/?serial=[序號]&code=[驗證碼]`
   - 例：`http://172.28.232.36:8800/register/?serial=PI-12345678&code=ABC123`

2. **用戶掃碼**

   - 掃描 QR Code → 導向「用戶註冊與開通設備頁」
   - 系統自動填入序號與驗證碼到表單中

3. **驗證設備資訊**

   - 系統驗證序號與驗證碼是否匹配
   - 確認設備尚未被綁定（`is_bound=False`）
   - 確認為合法擁有者，避免隨意綁定

4. **綁定帳號 + 開通設備**

   - 建立 `Device.user_id = request.user.id`，並將設備設為啟用（`is_bound=True`）
   - 系統發送綁定成功通知給使用者

5. **設備狀態同步**

   - 設備透過 API 定期 ping 伺服器回報狀態（`/api/device/ping/`）
   - 系統記錄設備 IP 與最後 ping 時間，用於判斷線上狀態

6. **雙向綁定完成**
   - 使用者可在平台控制設備
   - 設備可透過 API 回報狀態與接收指令

---

## 群組層級角色（群組成員角色）

- **群組擁有者**：建立群組的使用者，擁有該群組的最高權限
- **群組 Admin**：被群組擁有者指派的群組管理員，可管理群組內設備和成員
- **群組 Operator**：群組操作員，可控制群組內設備（可透過 ACL 限制特定設備）
- **群組 Viewer**：群組觀察員，只能查看群組資訊，無法控制設備

### 群組權限比較表

| 權限項目          | 群組擁有者 | 群組 Admin | 群組 Operator | 群組 Viewer |
| ----------------- | ---------- | ---------- | ------------- | ----------- |
| 查看群組資訊      | ✅         | ✅         | ✅            | ✅          |
| 控制群組內設備    | ✅         | ✅         | ✅            | ❌          |
| 管理群組成員      | ✅         | ✅         | ❌            | ❌          |
| 指派群組角色      | ✅         | ✅         | ❌            | ❌          |
| 新增/移除群組設備 | ✅         | ✅         | ❌            | ❌          |
| 設定設備 ACL 權限 | ✅         | ✅         | ❌            | ❌          |
| 刪除群組          | ✅         | ❌         | ❌            | ❌          |

\*群組 Operator 的設備控制權限可透過 ACL（存取控制清單）進一步限制特定設備

---

## 模組功能概覽（實際實作）

> 實作細節以 `pi_devices/`、`notifications/` 與前端 `templates/`、`static/` 內容為準。

- **電子鎖控制**
  - 遠端開鎖/上鎖（透過伺服馬達控制）
  - 自動上鎖延遲設定
  - LED 狀態指示（綠燈/紅燈）
  - 按鈕手動控制
- **監控攝影**
  - HLS 即時串流（低延遲）
  - 攝影機啟動/停止控制
  - 串流代理服務（透過 IP 代理）
- **智能照明**
  - LED 開關控制
  - 照度感測器自動控制（BH1750）
  - 自動開燈/關燈（基於環境亮度）
- **系統監控**
  - 設備線上狀態監控
  - 樹梅派系統指標（CPU、記憶體、溫度）
  - 設備心跳檢測

---

## 頁面與操作流程（整理版）

> 頁面實作以 `templates/` 及 `HomePiWeb/urls.py` 與各 app `urls.py` 為準。

1. 登入頁（含忘記密碼）
2. 註冊頁（SuperAdmin / 一般成員）
3. 重設密碼頁（驗證後設定新密碼）
4. 修改會員資料頁（依權限顯示欄位）
5. 設備開通頁（QR 驗證 + 權限設定整合）
6. 前台設備控制頁（首頁）：狀態、開關、控制
7. 群組列表 + 建立/編輯共用頁
8. 成員列表 + 邀請/移除（modal 操作）
9. 設備列表 + 設定共用頁（展開編輯）
10. 忘記密碼（SuperAdmin）頁：設備初始化流程
11. 授權管理頁：授權 Admin、共享設備
12. 加入群組頁：接受/拒絕邀請
13. 訊息通知頁：系統通知紀錄

常見流程摘要：

- **設備綁定（已登入）**：掃 QR → 填入序號/驗證碼 → 確認綁定 → 完成
- **設備綁定（未登入）**：掃 QR → 註冊帳號 → 自動綁定設備 → 完成
- **群組管理**：建立/編輯/刪除群組，管理群組成員與設備權限
- **邀請成員**：產生一次性邀請連結（可限定 email），設定角色與設備權限
- **接受邀請**：點邀請連結 → 登入/註冊 → 自動加入群組 → 完成
- **設備分享**：群組管理員可授權成員將自己的設備加入群組

忘記密碼情境：

- SuperAdmin：可觸發設備初始化（清除設備綁定，重新掃碼註冊）
- Admin/User：發送重設請求給 SuperAdmin，或以預設密碼流程重設

---

## 系統技術架構（現況）

| 類別       | 技術/工具                                              |
| ---------- | ------------------------------------------------------ |
| 前端       | Django Templates + 原生 JS/CSS（`static/home_pi_web`） |
| 後端       | Python + Django + DRF（REST API）                      |
| 主資料庫   | PostgreSQL（透過環境變數設定）                         |
| 日誌資料庫 | MongoDB（`homepi_logs`，用於設備 ping 日誌）           |
| 樹梅派     | `pi_agent`（HTTP 代理、HLS 串流、裝置偵測/控制、排程） |
| 虛擬環境   | Conda（`environment.yml`）                             |
| 通知       | `notifications/` app（支援 dedup/已讀/過期）           |
| 靜態檔案   | WhiteNoise（靜態檔案服務）                             |

備註：

- 主資料庫使用 PostgreSQL，透過環境變數設定連線參數
- MongoDB 用於儲存設備 ping 日誌等非關聯性資料
- 已安裝 Redis、Django Channels 等套件，但目前未啟用相關功能
- 若未來需要快取或即時通訊功能，可啟用 Redis 快取和 Channels WebSocket 支援

---

## 資料結構

完整細節可參考 `專案資料結構文件.md`。以下整理常用模型與欄位（現況）：

### 1. 使用者系統（users）

#### User

| 欄位          | 類型              | 說明                        |
| ------------- | ----------------- | --------------------------- |
| email         | EmailField        | 登入帳號，唯一              |
| role          | CharField         | 角色：user/admin/superadmin |
| invited_by    | ForeignKey(User)  | 邀請人，可空                |
| member_groups | ManyToMany(Group) | 所屬群組（透過 Membership） |
| is_active     | BooleanField      | 啟用狀態                    |
| is_staff      | BooleanField      | 可登入 admin                |
| date_joined   | DateTimeField     | 註冊時間                    |

主要方法：`is_online()`、`online_badge()`、`is_admin()`、`is_superadmin()`

---

### 2. 群組系統（groups）

#### Group

| 欄位       | 類型               | 說明                  |
| ---------- | ------------------ | --------------------- |
| name       | CharField          | 群組名稱              |
| owner      | ForeignKey(User)   | 群組擁有者            |
| devices    | ManyToMany(Device) | 透過 GroupDevice 關聯 |
| created_at | DateTimeField      | 建立時間              |

#### GroupMembership（unique: user+group）

| 欄位      | 類型              | 說明                  |
| --------- | ----------------- | --------------------- |
| user      | ForeignKey(User)  | 成員                  |
| group     | ForeignKey(Group) | 群組                  |
| role      | CharField         | admin/operator/viewer |
| joined_at | DateTimeField     | 加入時間              |

#### GroupDevice（unique: group+device）

| 欄位     | 類型               | 說明         |
| -------- | ------------------ | ------------ |
| group    | ForeignKey(Group)  | 群組         |
| device   | ForeignKey(Device) | 裝置         |
| added_by | ForeignKey(User)   | 添加者，可空 |
| added_at | DateTimeField      | 添加時間     |
| note     | CharField          | 備註，可空   |

#### DeviceShareRequest

| 欄位        | 類型               | 說明                      |
| ----------- | ------------------ | ------------------------- |
| requester   | ForeignKey(User)   | 申請人                    |
| group       | ForeignKey(Group)  | 目標群組                  |
| device      | ForeignKey(Device) | 分享裝置                  |
| message     | CharField          | 訊息，可空                |
| status      | CharField          | pending/approved/rejected |
| reviewed_by | ForeignKey(User)   | 審核人，可空              |
| reviewed_at | DateTimeField      | 審核時間，可空            |
| created_at  | DateTimeField      | 申請時間                  |

#### GroupShareGrant（active unique: user+group）

| 欄位       | 類型              | 說明         |
| ---------- | ----------------- | ------------ |
| user       | ForeignKey(User)  | 被授予者     |
| group      | ForeignKey(Group) | 群組         |
| created_by | ForeignKey(User)  | 授予者，可空 |
| created_at | DateTimeField     | 授予時間     |
| expires_at | DateTimeField     | 過期，可空   |
| is_active  | BooleanField      | 是否啟用     |

#### GroupDevicePermission（unique: user+group+device）

| 欄位        | 類型               | 說明       |
| ----------- | ------------------ | ---------- |
| user        | ForeignKey(User)   | 使用者     |
| group       | ForeignKey(Group)  | 群組       |
| device      | ForeignKey(Device) | 裝置       |
| can_control | BooleanField       | 是否可控制 |
| updated_at  | DateTimeField      | 更新時間   |

---

### 3. 邀請系統（invites）

#### Invitation

| 欄位       | 類型               | 說明                    |
| ---------- | ------------------ | ----------------------- |
| group      | ForeignKey(Group)  | 目標群組                |
| invited_by | ForeignKey(User)   | 邀請人                  |
| email      | EmailField         | 邀請信箱，可空          |
| role       | CharField          | 預設角色（如 operator） |
| max_uses   | PositiveInteger    | 最大使用次數，可空      |
| used_count | PositiveInteger    | 已使用次數              |
| expires_at | DateTimeField      | 過期，可空              |
| is_active  | BooleanField       | 是否啟用                |
| code       | CharField          | 邀請碼，唯一            |
| device     | ForeignKey(Device) | 關聯裝置，可空          |
| created_at | DateTimeField      | 建立時間                |

方法：`is_valid()`、`consume()`

#### InvitationDevice（unique: invitation+device）

| 欄位        | 類型                   | 說明       |
| ----------- | ---------------------- | ---------- |
| invitation  | ForeignKey(Invitation) | 邀請       |
| device      | ForeignKey(Device)     | 裝置       |
| can_control | BooleanField           | 是否可控制 |

---

### 4. 裝置系統（pi_devices）

#### Device

| 欄位              | 類型             | 說明                          |
| ----------------- | ---------------- | ----------------------------- |
| serial_number     | CharField        | 裝置序號（唯一，PI-XXXXXXXX） |
| verification_code | CharField        | 驗證碼（QR 綁定）             |
| token             | CharField        | 註冊 Token（唯一）            |
| user              | ForeignKey(User) | 擁有者，可空                  |
| is_bound          | BooleanField     | 是否已綁定                    |
| created_at        | DateTimeField    | 建立時間                      |
| ip_address        | GenericIPAddress | IP 位址，可空                 |
| last_ping         | DateTimeField    | 最後心跳（索引）              |
| display_name      | CharField        | 顯示名稱，可空                |
| is_streaming      | BooleanField     | 是否在串流                    |
| last_hls_url      | URLField         | 最後 HLS URL，可空            |

屬性/方法：`is_online()`、`name()`、`label`

#### DeviceCommand

| 欄位       | 類型               | 說明                              |
| ---------- | ------------------ | --------------------------------- |
| device     | ForeignKey(Device) | 目標裝置                          |
| command    | CharField          | 命令名稱                          |
| payload    | JSONField          | 參數                              |
| req_id     | CharField          | 請求 ID（索引）                   |
| status     | CharField          | pending/taken/done/failed/expired |
| error      | TextField          | 錯誤訊息，可空                    |
| created_at | DateTimeField      | 建立時間                          |
| taken_at   | DateTimeField      | 執行時間，可空                    |
| done_at    | DateTimeField      | 完成時間，可空                    |
| expires_at | DateTimeField      | 過期，可空                        |

#### DeviceCapability（unique: device+slug）

| 欄位         | 類型               | 說明                     |
| ------------ | ------------------ | ------------------------ |
| device       | ForeignKey(Device) | 所屬裝置                 |
| kind         | CharField          | 功能類型（如 light/fan） |
| name         | CharField          | 功能名稱                 |
| slug         | SlugField          | 功能代碼（裝置內唯一）   |
| config       | JSONField          | 配置                     |
| order        | PositiveInteger    | 顯示順序                 |
| enabled      | BooleanField       | 是否啟用                 |
| cached_state | JSONField          | 快取狀態                 |

#### DeviceSchedule

| 欄位       | 類型               | 說明                         |
| ---------- | ------------------ | ---------------------------- |
| device     | ForeignKey(Device) | 目標裝置                     |
| action     | CharField          | 動作名稱                     |
| payload    | JSONField          | 參數                         |
| run_at     | DateTimeField      | 執行時間（索引）             |
| status     | CharField          | pending/done/canceled/failed |
| error      | TextField          | 錯誤，可空                   |
| created_at | DateTimeField      | 建立時間                     |
| done_at    | DateTimeField      | 完成，可空                   |

---

### 5. 通知系統（notifications）

#### Notification

| 欄位                | 類型                    | 說明                    |
| ------------------- | ----------------------- | ----------------------- |
| user                | ForeignKey(User)        | 收件人                  |
| kind                | CharField               | 通知類型：member/device |
| event               | CharField               | 事件類型（索引）        |
| title               | CharField               | 標題                    |
| body                | TextField               | 內容，可空              |
| target_content_type | ForeignKey(ContentType) | 目標類型，可空          |
| target_object_id    | CharField               | 目標 ID，可空           |
| target              | GenericForeignKey       | 目標物件                |
| group               | ForeignKey(Group)       | 關聯群組，可空          |
| device              | ForeignKey(Device)      | 關聯裝置，可空          |
| is_read             | BooleanField            | 是否已讀（索引）        |
| read_at             | DateTimeField           | 讀取時間，可空          |
| dedup_key           | CharField               | 去重鍵，可空            |
| created_at          | DateTimeField           | 建立時間（索引）        |
| expires_at          | DateTimeField           | 過期，可空              |
| meta                | JSONField               | 額外資訊                |

方法：`is_expired`、`is_valid()`、`mark_read()`、`mark_unread()`；類別方法：`mark_all_for_user()`、`purge_expired()`

---

### 索引與效能建議（摘要）

- 外鍵預設索引；核心查詢加上複合索引：
  - `DeviceCommand(device, status, created_at)`
  - `Notification(user, is_read, created_at)`、`Notification(kind, event)`
  - `Device.last_ping`、`DeviceCapability(device, kind)`
  - 權限查詢：`GroupDevicePermission(group, user)`

---

## 通知機制（摘要）

- 分類：會員/群組通知、設備通知
- 功能：已讀狀態、去重鍵、過期時間、批次標記
- 範例：設備設定成功、加入/移除成員、授權成功、群組異動、綁定/開通信件（可擴充）
