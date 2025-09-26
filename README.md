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

- 前端靜態資源位於 `static/home_pi_web/`
- Django 模板位於 `templates/`
- 若有使用 `collectstatic`（生產環境）：

```bash
python manage.py collectstatic --noinput
```

---

## 樹梅派 Agent（pi_agent）

`pi_agent/` 提供裝置偵測、HTTP 代理、HLS 串流與排程等服務，設定檔位於 `pi_agent/config/homepi.yml`。

### 1. 在樹梅派建立環境

```bash
# 將專案同步到樹梅派後，在樹梅派上：
cd ~/HomePiWeb
conda env create -n homepi -f pi_agent/environment.yml
conda activate homepi
```

### 2. 測試執行 HTTP 代理與 HLS 串流

```bash
# 啟動 HTTP 代理（測試）
python pi_agent/http_agent.py

# 啟動 HLS 串流（測試）
python pi_agent/serve_hls.py
```

### 3. 設定 systemd 服務（生產建議）

專案內含服務範本（`pi_agent/說明文件/systemd檔案/`）：

- `homepi-http-agent@.service`
- `homepi-hls@.service`
- `homepi-hls-www@.service`
- `homepi-scheduler@.service`

請依照 `pi_agent/說明文件/*.md` 指南安裝與啟用。

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
- 發 PR 時請附上：
  - 功能說明與影響範圍
  - 測試結果（含手動測試步驟或自動化測試輸出）
  - 若涉及 DB 遷移或設定變更，請明確說明

---

## 常見問題與故障排除

- Wi-Fi/網路不穩：參考 `解決wifi浮動辦法們.md`
- 樹梅派功能與環境設定：參考 `pi_agent/說明文件/` 內各章節
- 專案結構與說明：`專案資料結構文件.md`

---

## 授權

未指定，請依內部政策或後續補充。

---

## 設備開通與綁定流程（QR 綁定）

以下為設備出廠到使用者綁定的標準流程：

1. 設備出廠
   - 樹梅派（或 ESP32）具唯一設備 ID、初始密碼與 QR Code（可編碼為網址 + token）
   - 例：`https://example.com/bind?token=abc123`
2. 用戶掃碼
   - 掃描 QR Code → 導向「用戶註冊與開通設備頁」
3. 驗證設備密碼
   - 確認為合法擁有者，避免隨意綁定
4. 綁定帳號 + 開通設備
   - 建立 `Device.user_id = request.user.id`，並將設備設為啟用
5. 通知樹梅派設備
   - 後端對設備 IP 發送 ping/POST，讓設備得知「被誰開通」
   - 可做簡易 handshake，例如 `POST /register`
6. 設備登入平台 / 記錄狀態
   - 樹梅派儲存使用者或回報平台，建立雙向綁定

---

## 角色與權限

### 角色定義

- SuperAdmin：擁有裝置密碼者，最高權限（單台裝置只有一位）。可管理群組、指派 Admin、管理設備參數
- Admin：被授權管理設備者，協助設定設備參數，不可管理群組或指派權限
- User：一般使用者，受邀加入，只能進行基本操作

### 權限比較表

| 權限項目                             | User | Admin | SuperAdmin |
| ------------------------------------ | ---- | ----- | ---------- |
| 操作智能家電                         | ✅   | ✅    | ✅         |
| 編輯個人資料                         | ✅   | ✅    | ✅         |
| 設定設備參數（基本，如風速）         | ✅   | ✅    | ✅         |
| 設定設備參數（環境，如自動觸發條件） | ❌   | ✅    | ✅         |
| 設備重命名                           | ❌   | ✅    | ✅         |
| 成員邀請 / 建立註冊頁                | ❌   | ❌    | ✅         |
| 成員加入審核 / 通知查看              | ❌   | ❌    | ✅         |
| 指定/取消 Admin 權限                 | ❌   | ❌    | ✅         |
| 群組建立 / 刪除                      | ❌   | ❌    | ✅         |

---

## 模組功能概覽（示意）

> 實作細節以 `pi_devices/`、`notifications/` 與前端 `templates/`、`static/` 內容為準。

- 解鎖（電子鎖）
  - 人臉辨識（規劃中/可擴充）
  - 遠端解鎖
  - 安全參數：高/低安全等級（雙重驗證、免驗證等）
  - 進出紀錄：次數統計、在家名單、總人數
- 監控 / 錄影
  - 即時監控、HLS 串流
  - 自動錄影時段、解析度設定、回放
  - 通知：記憶卡空間、週期上傳縮時等
- 智能家電
  - 電風扇：開關/方向/風速、溫度自動控制、耗電統計
  - 電燈：開關/亮度、照度自動控制、耗電統計

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

- 新設備開通（會員）：掃 QR → 驗密碼 → 權限設定（是否群組共享）→ 完成 → 發通知
- 新設備開通（未註冊）：掃 QR → 註冊 → 驗密碼 → 綁定 → 完成 → 發通知
- 後台群組管理：建立/編輯/刪除群組（刪除需再次驗證與提醒）
- 邀請成員：產生一次性、時效性邀請連結（Email/Line 自行整合）
- 成員移除：需 SuperAdmin 密碼確認 → 發送通知
- 加入群組：點邀請連結 → 確認加入或拒絕

忘記密碼情境：

- SuperAdmin：可觸發設備初始化（清除設備綁定，重新掃碼註冊）
- Admin/User：發送重設請求給 SuperAdmin，或以預設密碼流程重設

---

## 系統技術架構（現況）

| 類別     | 技術/工具                                              |
| -------- | ------------------------------------------------------ |
| 前端     | Django Templates + 原生 JS/CSS（`static/home_pi_web`） |
| 後端     | Python + Django（可逐步擴充 DRF）                      |
| 資料庫   | SQLite（開發）；可改 MySQL/PostgreSQL（生產）          |
| 樹梅派   | `pi_agent`（HTTP 代理、HLS 串流、裝置偵測/控制、排程） |
| 虛擬環境 | Conda（`environment.yml`）                             |
| 通知     | `notifications/` app（支援 dedup/已讀/過期）           |

備註：舊版文件提及 Node.js + React + DRF 套件，現況以 Django Template 為主；若未來導入前端框架，可在 `/api` 提供 DRF JSON 介面並保留原模板。

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
- 功能：已讀狀態、去重鍵、過期時間、批次標記、清理過期
- 範例：設備設定成功、加入/移除成員、授權成功、群組異動、綁定/開通信件（可擴充）
