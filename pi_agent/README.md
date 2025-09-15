## pi_agent — 樹梅派端 Agent 說明（初心者友善版）

這個目錄放的是「跑在樹梅派上的 Agent」，負責：

- 與後端伺服器溝通（心跳上報、拉取指令、回報結果）
- 控制本地硬體（LED、相機 HLS 串流、BH1750 照度感測器）
- 執行自動化（自動感光開關燈）與本地排程

本文會帶你快速了解檔案用途、如何安裝、怎麼跑起來，以及常見設定方式。

### 目錄結構

```text
pi_agent/
  config/              # 設定檔：YAML 與能力清單
  detect/              # 硬體自動偵測（I2C/One-wire 等）
  devices/             # 硬體裝置驅動（LED、BH1750、Camera）
  stream/              # 本地 HLS 服務（供直播串流使用）
  utils/               # 工具：HTTP 封裝、指標收集、排程器、自動感光
  http_agent.py        # 主程式（心跳/指令/自動感光/排程）
  serve_hls.py         # 啟動本地 HLS 服務的入口（若需要）
  environment.yml      # conda 環境定義
  說明文件/            # 更詳細的部署與 systemd 說明
```

---

## 安裝與環境準備（macOS 或 Raspberry Pi 5）

以下以 conda 建議流程為例（符合你的專案規範）：

```bash
# 1) 進入專案根目錄（包含 pi_agent/）
cd /Users/qkauia/Desktop/HomePiWeb

# 2) 建立/啟用 conda 環境（建議 Python 3.11+）
conda env create -f pi_agent/environment.yml
conda activate homepi-agent

# 3) 若使用 .env，建立環境變數（下方有範例）
cp -n pi_agent/env .env  # 若已存在請自行編輯
```

### .env（環境變數）

`utils/http.py` 會讀取以下變數：

```bash
# 樹梅派本機的裝置序號與 token（跟後端註冊配對）
SERIAL=PI-XXXXXXXX
TOKEN=your-device-token

# 後端服務位址（Django）
API_BASE=http://<server-ip>:8800

# （選）LED 預設腳位與極性，若未使用 YAML
LED_PIN=17
LED_ACTIVE_HIGH=true
```

### YAML 設定（可選，但建議）

`config/homepi.yml` 由 `config/loader.py` 讀取，用來定義 GPIO 工廠、裝置與自動化。

```yaml
# pi_agent/config/homepi.yml
gpio_factory: lgpio # 或 rpigpio 等（不確定可先不填）

devices:
  # LED 定義（可多顆）
  - name: led_1
    kind: led
    config:
      pin: 17
      active_high: true

  # BH1750 照度感測器
  - name: bh1750-1-0x23 # 命名建議：bh1750-<bus>-<addr>
    kind: bh1750
    config:
      bus: 1
      addr: 0x23

  # 電子鎖（按鈕+伺服馬達+雙LED）
  - name: locker_1
    kind: locker
    config:
      button_pin: 27 # 按鈕腳位
      servo_pin: 18 # 伺服馬達腳位
      led_green: 23 # 開鎖指示燈（綠）
      led_red: 22 # 上鎖指示燈（紅）
      auto_lock_delay: 10 # 自動上鎖延遲（秒）

auto_light:
  enabled: false # true 開啟自動感光
  sensor: bh1750-1-0x23 # 對應上面 devices 的 name
  led: led_1 # 要控制的 LED 名稱
  on_below: 80.0 # 低於此照度連續 N 次 → 開燈
  off_above: 120.0 # 高於此照度連續 N 次 → 關燈
  sample_every_ms: 1000 # 每幾毫秒取樣一次
  require_n_samples: 3 # 連續多少次符合才切換（去抖動）
```

> 小提醒：若未提供 YAML，也可用 `.env` 的 `LED_PIN/LED_ACTIVE_HIGH` 控制單顆 LED（會以預設名稱 `led_1` 存取）。

---

## 如何啟動

### 1) 跑主程式（Http Agent）

```bash
conda activate homepi-agent
python -m pi_agent.http_agent
```

主程式會定期：

- `ping`：上報心跳、系統指標（CPU/Memory/Temperature）、目前能力與狀態
- `pull`：長輪詢拉取待執行指令（如開關燈、開始/停止直播、啟用/停用自動感光）
- `ack`：回報指令執行結果與最新狀態（方便前端即時更新）
- `schedules`：抓取近期排程並交由本地排程器執行

### 2) 跑本地 HLS 服務（若用到相機直播）

`stream/http_hls.py` 會在本機提供 HLS 檔案（m3u8/ts）。Django 端有 `hls_proxy` 反向代理對外。

常見做法是用 systemd 跑（見下一節「systemd 範例」）。

---

## 重要模組簡介

### utils/http.py（HTTP 封裝）

- `ping(extra)`：心跳上報；`extra` 可帶 `caps`（能力清單）、`state`（裝置狀態）、`metrics`（系統指標）
- `pull(max_wait)`：長輪詢等待伺服器指令
- `ack(req_id, ok, error, state)`：回報指令執行結果與最新狀態
- `fetch_schedules()` / `schedule_ack(...)`：拉取與回報排程

> 這些 API 會使用 `.env` 的 `SERIAL/TOKEN/API_BASE` 自動帶入身分。

### http_agent.py（主流程）

- 啟動時載入 YAML、設定 GPIO 工廠、初始化 LED
- 呼叫 `detect/discover_all()` 蒐集裝置能力（caps）供前端渲染
- 迴圈內：定時 `ping`、拉取 `pull` 指令、執行並 `ack`
- 支援指令：
  - `light_on/light_off/light_toggle`
  - `camera_start/camera_stop`（搭配 HLS）
  - `locker_lock/locker_unlock/locker_toggle`（電子鎖控制）
  - `auto_light_on/auto_light_off`（啟用/停用自動感光）
  - `rescan_caps`（重新偵測能力並回報）
- 透過 `utils.metrics.get_pi_metrics()` 上報 CPU/記憶體/溫度
- 內建本地排程器 `utils.scheduler.LocalScheduler`（自動抓取排程並在背景執行）

### utils/auto_light.py（自動感光）

- 背景執行緒持續讀取 BH1750 值，根據門檻與去抖動條件切換 `devices/led.py`
- 外部可呼叫：
  - `start_auto_light(cfg)` / `stop_auto_light(wait=True)`
  - `get_state()`：提供目前 `running/last_lux/led_is_on/last_change_ts`
  - `set_state_push(callback)`：切換時即時回推狀態（`http_agent` 會用它主動 `ping`）

### devices/

- `led.py`：多顆 LED 控制；有 `setup_led()`、`light_on/off/toggle()`、`is_on()`，在沒有 `gpiozero` 時會退化為 no-op（但維持陰影狀態）
- `bh1750.py`：BH1750 驅動，採 one-shot 讀值、遇到 I2C 例外會嘗試恢復
- `camera.py`：相機/HLS 控制（由 `http_agent` 的 `camera_start/stop` 指令呼叫）
- `locker.py`：電子鎖控制；支援按鈕手動操作、自動上鎖、雙 LED 狀態指示、伺服馬達角度控制

### detect/

- `registry.py` 會整合 `hat.py/i2c.py/one_wire.py` 等，回傳能力清單（`caps`），例如有哪些 LED、感測器或相機

### stream/http_hls.py（HLS 服務）

- 在本機提供 `index.m3u8` 與分段 `*.ts`，Django 端的 `/hls/<serial>/...` 會反代到樹梅派 IP 的 8088 埠

---

## 常見操作範例

### 啟用自動感光（從後端送指令）

後端會透過 `/api/device/pull/` 下發指令，如：

```json
{
  "cmd": "auto_light_on",
  "req_id": "...",
  "payload": {
    "slug": "living-light",
    "sensor": "bh1750-1-0x23",
    "led": "led_1",
    "on_below": 80.0,
    "off_above": 120.0,
    "sample_every_ms": 1000,
    "require_n_samples": 3
  }
}
```

Agent 會：

- 重新套用 YAML 與 payload 的合併設定
- 確保 LED 初始化、停掉舊執行緒再以新參數重啟
- 在每次真的「開/關燈」時，主動 `ping` 把狀態推回伺服器

### 電子鎖控制（從後端送指令）

後端會透過 `/api/device/pull/` 下發指令，如：

```json
{
  "cmd": "locker_unlock",
  "req_id": "...",
  "payload": {
    "target": "locker_1",
    "slug": "main-door"
  }
}
```

支援的指令：

- `locker_lock`：上鎖
- `locker_unlock`：開鎖（會啟動自動上鎖計時器）
- `locker_toggle`：切換鎖定狀態

Agent 會：

- 執行對應的鎖定動作
- 回報最新狀態（locked、auto_lock_running 等）
- 自動上鎖功能會在開鎖後 N 秒自動上鎖（可透過 YAML 或 payload 設定）

### 本地排程（開/關燈）

Agent 會定期呼叫後端 `/api/device/schedules/` 取得未來的排程（只要時間到點會在本機執行，並 `schedule_ack` 回報結果）。

---

## systemd 服務（樹梅派）

範例檔在 `pi_agent/說明文件/systemd檔案/`，可參考：

- `homepi-agent@.service`：主程式（http_agent）
- `homepi-hls@.service`：攝影機推流服務
- `homepi-hls-http@.service` / `homepi-hls-www@.service`：本地 HLS 靜態服務
- `homepi-scheduler@.service`：排程服務（若拆成獨立程序）

基本操作：

```bash
# 安裝服務檔（需 root）
sudo cp pi_agent/說明文件/systemd檔案/*.service /etc/systemd/system/
sudo cp pi_agent/說明文件/systemd檔案/*.timer /etc/systemd/system/

# 重新載入並啟動
sudo systemctl daemon-reload
sudo systemctl enable homepi-agent@pi.service
sudo systemctl start homepi-agent@pi.service

# 查看狀態/日誌
systemctl status homepi-agent@pi.service
journalctl -u homepi-agent@pi.service -f
```

> 將 `@pi` 視為你的執行者名稱或目錄代稱，可依實際需求調整服務檔內的 `ExecStart` 與環境。

---

## 疑難排解（簡短版）

- LED 沒反應？
  - 先確認是否安裝 `gpiozero`，或 YAML 是否正確（腳位/極性）
  - 若在 macOS 或無 GPIO 的環境會進入 no-op，只會印訊息（屬預期）
- BH1750 讀不到？
  - 檢查 I2C 是否啟用、位址是否 0x23/0x5C，線路是否正確
  - 程式會嘗試自動恢復，仍為 None 代表硬體或接線需檢查
- 後端收不到心跳？
  - 檢查 `.env` 的 `SERIAL/TOKEN/API_BASE` 是否正確
  - `ping`/`pull`/`ack` 逾時多半是網路/防火牆或伺服器位址錯誤

---

## 版本控制與規範

- 程式碼風格：PEP8 + Black，自動格式化；import 採 isort 規範
- Git 提交：Conventional Commits（feat:/fix:/docs: ...）
- 文件：一律正體中文，Markdown 標題階層正確，重要程式碼片段附上用途說明

---

## 小結

想快速開始：

1. 建立 conda 環境並啟用

2. 準備 `.env`（必填：`SERIAL/TOKEN/API_BASE`）

3. （建議）設定 `config/homepi.yml` 定義 LED 與感測器

4. 執行 `python -m pi_agent.http_agent`

需要直播，另外用 systemd 跑 HLS 服務即可。
