<!-- markdownlint-disable -->

#### HomePi Agent 設定與擴充說明書

> 適用專案：`/home/qkauia/pi_agent`（Raspberry Pi）  
> 目的：把 **GPIO 腳位與裝置設定抽離到 YAML**，service 不再綁死硬體設定；日後新增裝置 **只改 YAML + 少量模組** 即可。

---

#### 說明建立裝置流程:

1. 把設定寫到：[pi_agent/config/homepi.yml](./config/homepi.yml)

2. 服務檔只啟動 `http_agent.py`，透過環境變數指到 `homepi.yml`：

   ```ini
   # /etc/systemd/system/homepi-agent.service
   [Unit]
   Description=HomePi HTTP Agent
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   User=qkauia
   WorkingDirectory=/home/qkauia/pi_agent
   Environment=PYTHONUNBUFFERED=1
   Environment=HOMEPI_CONFIG=/home/qkauia/pi_agent/config/homepi.yml
   ExecStart=/usr/bin/python3 /home/qkauia/pi_agent/http_agent.py
   Restart=always
   RestartSec=3

   [Install]
   WantedBy=multi-user.target
   ```

3. `http_agent.py` 在啟動時讀 YAML → 初始化裝置；舊 API 相容。

##### 追加裝置總結:

1. 修改 [pi_agent/config/homepi.yml](../config/homepi.yml)
2. (必要時)新增 `devices/<裝置名稱>.py`
   - 並在[pi_agent/http_agent.py](../http_agent.py)裡的`COMMANDS` 註冊即可。

---

## 目前專案目錄（重點）

```
pi_agent/
├─ config/
│  ├─ capabilities.json     ← 裝置建立寫入data
│  ├─ homepi.yml            ← 腳位變數設定
│  └─ loader.py             ← 設定載入器
├─ detect/
├─ devices/
│  ├─ led.py                ← 已改成支援 YAML + 多顆 LED
│  ├─ camera.py
│  └─ …
├─ utils/
│  └─ http.py               ← 與後端通訊（ping/pull/ack）
├─ http_agent.py            ← 主程式：分發指令
└─ homepi-agent.service*    ← 你保留的稿；真正的 service 放 /etc/systemd/system/
```

> **建議**：`config/` 內加一個空的 `__init__.py`，利於 IDE、自動完成與測試。

---

## 相依套件（建議）

```bash
# 若未裝：
sudo apt update
sudo apt install -y python3-gpiozero python3-lgpio

# 讀 YAML 設定檔
pip install pyyaml
```

- **PinFactory**（YAML 的 `gpio_factory`）：Pi 5 建議 `lgpio`。
- 你也可以用環境變數 `GPIOZERO_PIN_FACTORY` 覆寫。

---

## YAML 設定檔規格（`config/homepi.yml`）

```yaml
gpio_factory: lgpio # rpigpio / lgpio / pigpio ...

devices:
  # --- LED 範例 ---
  - name: led_1
    kind: led
    pin: 17
    active_high: true

  # - name: led_2
  #   kind: led
  #   pin: 23
  #   active_high: false

  # --- 按鈕範例 ---
  # - name: btn_1
  #   kind: button
  #   pin: 27
  #   pull_up: true
  #   bounce: 0.05

  # --- 繼電器範例 ---
  # - name: relay_1
  #   kind: relay
  #   pin: 24
  #   active_high: true

  # --- 攝影機（HLS）範例（若 camera.py 支援讀 YAML） ---
  # - name: cam_1
  #   kind: camera
  #   width: 1280
  #   height: 720
  #   framerate: 30
  #   hls_time: 2
  #   list_size: 6
  #   output_dir: ./stream
```

### 命名與型別

- `name`：裝置邏輯名稱（指令 `target` 會用到）。
- `kind`：裝置類型（`led`、`button`、`relay`、`camera`…）。
- 其餘欄位由各 `devices/<kind>.py` 自行解讀。

---

## 設定載入器（`config/loader.py`）

```python
# /home/qkauia/pi_agent/config/loader.py
import os
from pathlib import Path
import yaml

def load():
    """
    優先用 HOMEPI_CONFIG 指定的 YAML；否則 fallback 到 ./config/homepi.yml；
    讀不到就回傳 {}。
    """
    cfg_path = os.environ.get("HOMEPI_CONFIG")
    p = Path(cfg_path) if cfg_path else Path(__file__).resolve().parent / "homepi.yml"
    if p.is_file():
        with open(p, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}
```

> `http_agent.py` 只需要：
>
> ```python
> from config.loader import load as load_config
> CFG = load_config()
> ```

---

## 主程式（`http_agent.py`）如何吃設定

1. 設定 `GPIOZERO_PIN_FACTORY`（先於匯入裝置模組）：
   ```python
   import os
   from config.loader import load as load_config
   CFG = load_config()
   os.environ["GPIOZERO_PIN_FACTORY"] = CFG.get(
       "gpio_factory",
       os.environ.get("GPIOZERO_PIN_FACTORY", "lgpio")
   )
   ```
2. 再匯入裝置模組並初始化：
   ```python
   from devices import led, camera
   led.setup_led(CFG)  # 會解析 YAML；沒有 YAML 時回退環境變數 LED_PIN / LED_ACTIVE_HIGH
   ```
3. 指令分發表：
   ```python
   COMMANDS = {
       "light_on":    led.light_on,     # 可帶 target（ex: led_2），不帶則操作第一顆
       "light_off":   led.light_off,
       "light_toggle": led.light_toggle,
       "camera_start": camera.start_hls, # 若 camera.py 支援 target/name 亦可帶
       "camera_stop":  camera.stop_hls,
   }
   ```
4. （可選）若你想讓所有 handler 都支援 `{"target": "led_2"}`，可用 wrapper：
   ```python
   def _call_handler(handler, cmd):
       target = cmd.get("target") or cmd.get("name")
       try:
           if target is not None:
               return handler(target)
       except TypeError:
           pass
       return handler()
   ```

---

## 內建 LED 模組（`devices/led.py`）— 已改良版重點

- **多顆 LED**：由 YAML 建構 `_LEDS[name] = LED(pin, active_high=...)`
- **舊 API 相容**：`light_on/off/toggle()` 不帶參數 → 操作第一顆
- **無 gpiozero 環境**：no-op（只印訊息，不拋例外）

> 你已套用這個版本；若需要再看完整程式，可回到我們對話中的最後版本。

---

## 範例操作流程

### 範例 1：新增第二顆 LED（GPIO 23、低電位致能）

1. 改 `config/homepi.yml`
   ```yaml
   devices:
     - name: led_1
       kind: led
       pin: 17
       active_high: true
     - name: led_2
       kind: led
       pin: 23
       active_high: false
   ```
2. 重啟服務：
   ```bash
   sudo systemctl restart homepi-agent
   ```
3. 後端下指令（JSON 長輪詢協議）：
   ```json
   { "cmd": "light_on", "target": "led_2" }
   ```
   > 若後端目前不送 `target`，也可沿用舊法 `{"cmd": "light_on"}`（操作第一顆）。

---

### 範例 2：新增「按鈕」模組（`devices/button.py`）

1. 建立檔案：`devices/button.py`

   ```python
   # devices/button.py
   from typing import Dict, Optional
   import os
   try:
       from gpiozero import Button
   except Exception:
       Button = None

   _BTNS: Dict[str, Button] = {}

   def setup_button(cfg: Optional[dict] = None):
       cfg = cfg or {}
       devs = [d for d in cfg.get("devices", []) if d.get("kind") == "button"]
       if Button is None:
           print("[BTN] gpiozero 不可用（no-op）; parsed:", [d.get("name") for d in devs])
           return
       for i, d in enumerate(devs):
           name = d.get("name") or f"btn_{i+1}"
           pin = int(d["pin"])
           pull_up = bool(d.get("pull_up", True))
           bounce = float(d.get("bounce", 0.05))
           _BTNS[name] = Button(pin, pull_up=pull_up, bounce_time=bounce)
           print(f"[BTN] init ok: {name} (pin={pin}, pull_up={pull_up}, bounce={bounce})")

   def is_pressed(name: Optional[str] = None) -> bool:
       if not _BTNS:
           raise RuntimeError("No button initialized")
       btn = _BTNS.get(name) or next(iter(_BTNS.values()))
       return bool(getattr(btn, "is_pressed", False))
   ```

2. 在 `http_agent.py` 初始化：
   ```python
   from devices import button
   button.setup_button(CFG)
   ```
3. 在 `COMMANDS` 註冊查詢指令：
   ```python
   "button_status": lambda target=None: print("BTN pressed?", button.is_pressed(target)),
   ```
4. YAML 寫法：
   ```yaml
   - name: btn_1
     kind: button
     pin: 27
     pull_up: true
     bounce: 0.05
   ```

---

### 範例 3：新增「繼電器」模組（`devices/relay.py`）

1. 建立檔案：`devices/relay.py`

   ```python
   # devices/relay.py
   from typing import Dict, Optional
   try:
       from gpiozero import OutputDevice
   except Exception:
       OutputDevice = None

   _RELAYS: Dict[str, OutputDevice] = {}

   def setup_relay(cfg: Optional[dict] = None):
       cfg = cfg or {}
       devs = [d for d in cfg.get("devices", []) if d.get("kind") == "relay"]
       if OutputDevice is None:
           print("[RELAY] gpiozero 不可用（no-op）; parsed:", [d.get("name") for d in devs])
           return
       for i, d in enumerate(devs):
           name = d.get("name") or f"relay_{i+1}"
           pin = int(d["pin"])
           active_high = bool(d.get("active_high", True))
           _RELAYS[name] = OutputDevice(pin, active_high=active_high, initial_value=False)
           print(f"[RELAY] init ok: {name} (pin={pin}, active_high={active_high})")

   def on(name: Optional[str] = None):
       dev = _RELAYS.get(name) or next(iter(_RELAYS.values()))
       dev.on()

   def off(name: Optional[str] = None):
       dev = _RELAYS.get(name) or next(iter(_RELAYS.values()))
       dev.off()

   def toggle(name: Optional[str] = None):
       dev = _RELAYS.get(name) or next(iter(_RELAYS.values()))
       dev.toggle()
   ```

2. `http_agent.py`：

   ```python
   from devices import relay
   relay.setup_relay(CFG)

   COMMANDS.update({
       "relay_on": relay.on,
       "relay_off": relay.off,
       "relay_toggle": relay.toggle,
   })
   ```

3. YAML：
   ```yaml
   - name: relay_1
     kind: relay
     pin: 24
     active_high: true
   ```

---

## 與後端協議（長輪詢）— 指令格式建議

- Agent 端每 30 秒 `ping()`；第一次夾 `caps`（`detect.registry.discover_all()` 結果）。
- 透過 `pull(max_wait=20)` 取得指令，通常為：
  ```json
  { "req_id": "uuid", "cmd": "light_on", "target": "led_2" }
  ```
- 成功後以 `ack(req_id, ok=True)` 回報；失敗回傳 `ok=False, error="<msg>"`。

> **命名建議**：
>
> - `cmd`: 動作（如 `light_on`、`camera_start`）。
> - `target`: 裝置名稱（對應 YAML 的 `name`）。
> - 如無 `target`，Agent 應對應「第一顆/預設」裝置，保留舊版相容性。

---

## 測試流程

```bash
# 1) 直接以使用者身分跑（看 log）
cd /home/qkauia/pi_agent
python3 http_agent.py

# 2) systemd 方式跑
sudo systemctl daemon-reload
sudo systemctl enable --now homepi-agent
journalctl -u homepi-agent -f -n 200  # 追 log

# 3) 改完 YAML
sudo systemctl restart homepi-agent
```

---

## 疑難排解

- **無法載入 YAML**：`pip install pyyaml`。
- **gpiozero 錯誤**（非 Pi 或權限不夠）：模組會進入 **no-op**，不會 crash；請確認：
  - 使用者為 `qkauia`（service 檔 `User=qkauia`）。
  - 具備 GPIO 權限（Raspberry Pi OS 預設 ok）。
  - 若是 Pi 5，建議 `GPIOZERO_PIN_FACTORY=lgpio`（已可由 YAML 設定）。
- **指令沒有 `target`**：會操作第一顆（建立順序）；可在 log 查看「init ok: <name>」。
- **路徑問題**：建議在 `config/` 放 `__init__.py`，並用絕對路徑指定 `HOMEPI_CONFIG`。

---

## 變更紀錄（建議）

- 2025-08-27：導入 `config/homepi.yml` 與 `config/loader.py`；  
  `devices/led.py` 支援多顆 LED 與 YAML；`http_agent.py` 可帶 `target`。

---

## 下一步建議

- 將 `devices/camera.py` 也改為讀 YAML（解析解析度/幀率/HLS 參數）。
- 統一定義 `devices/*` 介面（`setup_*()` + 動作函式），命名規範與錯誤處理。
- 若有 staging / production 不同設定，可用不同 YAML 並透過 service 的 `HOMEPI_CONFIG` 切換。
