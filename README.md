<!-- markdownlint-disable -->

# 專案需求：Raspberry Pi 遠端操作平台（MySQL + phpMyAdmin 版本）

本專案目標為建立一個網站平台，讓使用者可遠端控制與監控 Raspberry Pi 模組，搭配學校 Apache 環境提供的 phpMyAdmin（MySQL）進行資料管理。

---

## 🔧 網站功能

### 📌 會員系統
- 註冊 / 登入
- 權限分級：
  - **管理員**
    - 管理會員
    - 設定模組時間參數
    - 查詢各 Raspberry Pi 主機資訊（記憶體 / 硬碟 / IP）
  - **普通會員**
    - 僅可操作模組

### 🖥️ 操作樹莓派（共 3 台）
- 選擇主機
- 選擇模組（共 3 組：解鎖 / 監控 / 智能家電）

#### 模組功能：
1. 解鎖：(人臉辨識)、遠端解鎖、進出紀錄、通知
2. 遠端監控:(室內/室外)、(人臉辨識)、錄影 / 播放、通知
3. 智能家電：電風扇 / 電燈開關、自動控制、耗電量統計

---

## 🧰 系統技術架構（本地開發）

| 類別       | 技術/工具                    |
|------------|-------------------------------|
| 前端       | Node.js + React               |
| 後端       | Python + Django + DRF         |
| 資料庫     | **MySQL（phpMyAdmin 管理）** |
| 通知服務   | Discord Bot（本機執行）       |
| 虛擬環境   | Poetry + `.venv`              |

> Django REST Framework 是一個 專門用來建立 API 的 Django 擴充工具包，幫助你把資料（例如資料庫中的模型）變成前端（例如 React）或其他裝置能讀懂的 JSON 格式 API。
---

## User（使用者）

| 欄位名稱   | 資料型別       | 說明                         |
|------------|----------------|------------------------------|
| id         | Integer (Primary Key) | 使用者主鍵 ID            |
| email      | EmailField     | 使用者信箱（唯一）           |
| password   | CharField(128) | 密碼（加密儲存）             |
| name       | CharField(50)  | 使用者姓名                   |
| is_admin   | BooleanField   | 是否為管理員                 |
| created_at | DateTimeField  | 註冊時間                     |

---

## RaspberryPi（樹莓派主機）

| 欄位名稱      | 資料型別       | 說明                         |
|---------------|----------------|------------------------------|
| id            | Integer (Primary Key) | 主鍵 ID              |
| name          | CharField(50)  | 主機名稱                    |
| ip_address    | IPAddressField | IP 位址                     |
| memory_status | CharField(50)  | 記憶體使用狀態               |
| storage_status| CharField(50)  | 硬碟使用狀態                 |
| created_at    | DateTimeField  | 建立時間                     |

---

## Module（模組）

| 欄位名稱     | 資料型別       | 說明                                     |
|--------------|----------------|------------------------------------------|
| id           | Integer (Primary Key) | 模組 ID                        |
| name         | CharField(20)  | 模組名稱（例如：解鎖 / 監控 / 家電）     |
| raspberry_pi | ForeignKey → RaspberryPi | 所屬的樹莓派主機（外鍵）        |

---

## OperationLog（操作紀錄）

| 欄位名稱       | 資料型別       | 說明                         |
|----------------|----------------|------------------------------|
| id             | Integer (Primary Key) | 紀錄 ID            |
| user           | ForeignKey → User      | 操作者（外鍵）         |
| module         | ForeignKey → Module    | 操作的模組（外鍵）     |
| action         | CharField(100) | 操作行為描述                 |
| timestamp      | DateTimeField  | 操作時間                     |
| additional_info| TextField      | 補充資訊（選填）             |

---

## UnlockSchedule / RecordSchedule（排程設定）

| 欄位名稱   | 資料型別       | 說明                         |
|------------|----------------|------------------------------|
| id         | Integer (Primary Key) | 主鍵 ID             |
| module     | ForeignKey → Module | 所屬模組（外鍵）   |
| start_time | TimeField      | 開始時間                     |
| end_time   | TimeField      | 結束時間                     |

---

## SmartDevice（智能裝置）

| 欄位名稱    | 資料型別       | 說明                         |
|-------------|----------------|------------------------------|
| id          | Integer (Primary Key) | 裝置 ID              |
| module      | ForeignKey → Module | 所屬模組（外鍵）       |
| device_type | CharField(10)  | 裝置類型（風扇、燈等）        |
| is_on       | BooleanField   | 開啟狀態                     |
| auto_mode   | BooleanField   | 自動控制                     |
| power_usage | FloatField     | 耗電量（kWh）                |
| updated_at  | DateTimeField  | 最後更新時間                 |

---

## Notification（通知）

| 欄位名稱   | 資料型別       | 說明                         |
|------------|----------------|------------------------------|
| id         | Integer (Primary Key) | 通知 ID             |
| user       | ForeignKey → User      | 接收者（外鍵）         |
| module     | ForeignKey → Module    | 所屬模組（外鍵）       |
| content    | TextField      | 通知內容                     |
| timestamp  | DateTimeField  | 發送時間                     |
| is_sent    | BooleanField   | 是否已發送                   |

---

## 📁 專案結構

```
rpi_control/
├── backend/
│   ├── config/（Django 設定）
│   ├── manage.py
│   └── apps/
│       ├── users/
│       ├── devices/
│       └── notifications/
├── frontend/
│   └── src/（React 元件與頁面）
├── .env
├── pyproject.toml
└── README.md
```

---

## 📦 Python 套件依賴

```toml
[tool.poetry.dependencies]
python = "^3.11"
django = "*"
djangorestframework = "*"
mysqlclient = "*"
python-decouple = "*"
discord.py = "*"
```

---

## 📄 .env 設定（對應 phpMyAdmin）

```env
SECRET_KEY=your-secret
DEBUG=True
DB_NAME=school_db
DB_USER=root
DB_PASSWORD=123456
DB_HOST=127.0.0.1
DB_PORT=3306
```

---

## ✅ 啟動方式（本地端）

```bash
# 啟動 Django 後端
source .venv/bin/activate
python manage.py runserver

# 啟動 React 前端
cd frontend
npm install
npm start
```

---

## 🔔 Discord Bot 結構建議

```
backend/apps/notifications/
├── discord_bot/
│   ├── bot.py
│   └── sender.py
```

>Bot 可本地運行，自資料庫中讀取事件通知使用者。

---

## 📌 注意事項

- 資料儲存於 Apache+MySQL
