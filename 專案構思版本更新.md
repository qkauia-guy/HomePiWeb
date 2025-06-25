<!-- markdownlint-disable -->

# 專案需求：Raspberry Pi 遠端操作平台

架設網站讓使用者可以透過網站達成樹莓派的操作。

## 🔧 網站功能

### 📌 會員系統
- 註冊 / 登入
- 權限分級：
  - **管理員**
    - 管理會員
    - 設定樹莓派模組時間參數
    - 查詢各樹莓派主機資訊（記憶體 / 硬碟容量 / IP ADDRESS）
  - **普通會員**
    - 僅可操作模組，不具備管理權限

### 🖥️ 操作樹莓派（共 3 台）
- 選擇操作主機
- 選擇操作模組（共 3 組）

#### 模組功能：
1. **解鎖**
   - 人臉辨識
   - 遠端解鎖
   - 解鎖時間設定
   - 進出紀錄
   - 通知（如 Discord bot）
2. **監控系統**
   - 人臉辨識
   - 遠端監控
   - 錄影 / 播放
   - 錄影時間設定
   - 通知
3. **智能家電**
   - 電風扇 / 電燈控制
     - 遠端開關
     - 自動控制
     - 耗電統計

## 🧰 系統技術架構

| 類別       | 技術/工具               |
|------------|--------------------------|
| 前端語言   | Node.js                  |
| 前端框架   | React                    |
| 後端語言   | Python3                  |
| 後端框架   | Django                   |
| 資料庫     | PostgreSQL               |
| 樹莓派裝置 | Raspberry Pi 5           |
| 鏡頭模組   | Raspberry Pi Camera 模組 |
| 通知服務   | Discord Bot              |
| 虛擬環境   | 未定|

---

# 🧱 資料結構設計

## 使用者系統

### User
| 欄位名稱       | 類型             | 說明         |
|----------------|------------------|--------------|
| id             | Integer (PK)     | 使用者 ID    |
| email          | EmailField       | 使用者信箱（唯一） |
| password       | CharField(128)   | 密碼（加密後） |
| name           | CharField(50)    | 使用者姓名    |
| is_admin       | BooleanField     | 是否為管理員 |
| created_at     | DateTimeField    | 註冊時間      |

---

## Raspberry Pi 主機資訊

### RaspberryPi
| 欄位名稱       | 類型             | 說明         |
|----------------|------------------|--------------|
| id             | Integer (PK)     | 主鍵 ID      |
| name           | CharField(50)    | Pi 名稱      |
| ip_address     | IPAddressField   | IP 位址      |
| memory_status  | CharField(50)    | 記憶體使用狀態 |
| storage_status | CharField(50)    | 硬碟使用狀態  |
| created_at     | DateTimeField    | 建立時間      |

---

## 模組系統

### Module
| 欄位名稱       | 類型             | 說明         |
|----------------|------------------|--------------|
| id             | Integer (PK)     | 模組 ID      |
| name           | CharField(20)    | 模組名稱（解鎖/監控/智能家電） |
| raspberry_pi   | FK → RaspberryPi | 所屬樹莓派     |

---

## 操作紀錄

### OperationLog
| 欄位名稱       | 類型             | 說明         |
|----------------|------------------|--------------|
| id             | Integer (PK)     | 紀錄 ID      |
| user           | FK → User        | 操作者       |
| module         | FK → Module      | 操作的模組    |
| action         | CharField(100)   | 操作行為     |
| timestamp      | DateTimeField    | 操作時間     |
| additional_info| TextField        | 補充資訊     |

---

## 解鎖模組設定

### UnlockSchedule
| 欄位名稱       | 類型             | 說明         |
|----------------|------------------|--------------|
| id             | Integer (PK)     | 主鍵         |
| module         | FK → Module      | 解鎖模組     |
| start_time     | TimeField        | 開始時間     |
| end_time       | TimeField        | 結束時間     |

---

## 監控模組設定

### RecordSchedule
| 欄位名稱       | 類型             | 說明         |
|----------------|------------------|--------------|
| id             | Integer (PK)     | 主鍵         |
| module         | FK → Module      | 監控模組     |
| start_time     | TimeField        | 錄影開始時間 |
| end_time       | TimeField        | 錄影結束時間 |

---

## 智能家電模組

### SmartDevice
| 欄位名稱       | 類型             | 說明         |
|----------------|------------------|--------------|
| id             | Integer (PK)     | 主鍵         |
| module         | FK → Module      | 所屬模組     |
| device_type    | CharField(10)    | 裝置類型（電風扇/電燈） |
| is_on          | BooleanField     | 是否開啟     |
| auto_mode      | BooleanField     | 自動控制模式 |
| power_usage    | FloatField       | 耗電量 (kWh) |
| updated_at     | DateTimeField    | 最後更新時間 |

---

## 通知系統

### Notification
| 欄位名稱       | 類型             | 說明         |
|----------------|------------------|--------------|
| id             | Integer (PK)     | 通知 ID      |
| user           | FK → User        | 收件者       |
| module         | FK → Module      | 所屬模組     |
| content        | TextField        | 通知內容     |
| timestamp      | DateTimeField    | 發送時間     |
| is_sent        | BooleanField     | 是否已發送   |

# Raspberry Pi 遠端操作平台：完整環境與專案架構說明（無 Docker）

## 💻 虛擬機建議（Windows / macOS 通用）

如不使用 Docker，推薦以下虛擬環境或工具來統一開發環境：

### ✅ Python 開發環境選項：
| 工具        | 系統相容 | 特點                    |
|-------------|----------|-------------------------|
| venv        | ✅ Win / Mac | Python 內建虛擬環境管理器 |
| pyenv + pyenv-virtualenv | ✅ Win (WSL) / Mac | 多版本管理、隔離環境     |
| Anaconda    | ✅ Win / Mac | 科學運算常用，較大但易用   |

### ✅ Node.js 開發環境建議：
| 工具 | 說明 |
|------|------|
| nvm  | Node.js 版本管理工具（推薦） |
| yarn / npm | 套件管理工具，皆可使用 |

---

## 📁 專案總體結構

```
rpi_control/
├── backend/                      # Django 專案後端
│   ├── manage.py
│   ├── config/                   # Django 設定（settings.py）
│   │   └── settings.py
│   └── apps/                     # 自訂 APPs
│       ├── users/                # 使用者管理（models, views, serializers）
│       ├── devices/              # Pi + 模組邏輯
│       └── notifications/        # Discord bot 通知
│
├── frontend/                     # React 前端專案
│   ├── public/
│   │   ├── index.html            # HTML 樣板檔
│   │   └── favicon.ico
│   └── src/
│       ├── index.js              # 進入點
│       ├── App.js                # 路由主框架
│       ├── pages/                # 各頁面元件
│       │   ├── Login.jsx
│       │   ├── Dashboard.jsx
│       │   └── RaspberryPi.jsx
│       ├── components/           # 可重用元件
│       │   ├── Navbar.jsx
│       │   ├── DeviceCard.jsx
│       │   └── PiSelector.jsx
│       ├── api/                  # axios 請求封裝
│       │   ├── auth.js
│       │   └── device.js
│       └── styles/               # CSS/SCSS 檔案
│           ├── App.css
│           ├── login.css
│           └── dashboard.css
│
├── requirements.txt              # Python 套件需求
├── package.json                  # Node.js 套件管理
├── .env                          # 環境變數
└── README.md
```

---

## 🌐 HTML / CSS / JS 說明

### 🔹 HTML
- 使用 React，主要 HTML 為：
  - `frontend/public/index.html`：掛載點，包含 `<div id="root"></div>`

### 🔹 CSS
- 建議使用 `frontend/src/styles/` 來管理所有樣式
- 可拆分頁面樣式如 `login.css`, `dashboard.css`
- 也可整合進 `App.css` 或改為 SCSS 架構（使用 `sass` 套件）

### 🔹 JavaScript / JSX
- 每個頁面為獨立 `.jsx` 元件
- 每個 API 對應一個 `axios` 請求檔，集中在 `api/`

---

## 🚀 專案初始化

### Python 後端

```bash
# 建立虛擬環境並啟動
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安裝套件
pip install -r requirements.txt

# 設定資料庫 & 遷移
python manage.py makemigrations
python manage.py migrate

# 啟動伺服器
python manage.py runserver
```

### Node.js 前端

```bash
cd frontend
npm install
npm start
```

---

## 🔔 Discord Bot 目錄建議（可整合於 backend/apps/notifications）

```
backend/apps/notifications/
├── discord_bot/
│   ├── __init__.py
│   ├── bot.py               # Bot 建立與命令處理
│   └── sender.py            # 發送訊息方法
└── utils.py                 # 實用函式
```

---

若需支援 WebSocket、定時任務（排程解鎖/錄影），可再加入：
- `Django Channels`
- `Celery + Redis`