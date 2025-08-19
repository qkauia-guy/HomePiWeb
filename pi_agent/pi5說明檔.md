<!-- markdownlint-disable -->

##### 設定 ping 到本地專案

####

1. `cd ~/home`
2. `mkdir pi`
3. `cd pi`
4. 將`pi_agent`資料夾移動到這`pi`目錄
5. 確認是否有`pi_agent/http_agent.py`檔案
6. 進入 shell 建立裝置：

```python
from pi_devices.models import Device

# 建立一筆新裝置
d = Device.objects.create()

print(d.id)                 # 新增後的 ID
print(d.serial_number)      # 系統自動產生的序號
print(d.verification_code)  # 自動產生的驗證碼
print(d.token)              # 自動產生的 Token
print(d.is_bound)           # 預設 False
print(d.created_at)         # 自動時間戳記
```

```python
# 進行轉換成註冊頁面QR CODE png
from pi_devices.utils.qrcode_utils import generate_device_qrcode
file_path = generate_device_qrcode(d)
print("QR Code 已儲存於：", file_path) # QR Code 已儲存於： /Users/qkauia/Desktop/HomePiWeb/static/qrcodes/PI-AA5CA0A5.png
```

```python
# http_agent.py:
import time, requests, json

SERIAL = "PI-E2390730"  # 需更換
TOKEN = "3de6279eae104e0b858b648dc659e9ba"  # 需更換
API_BASE = "http://172.28.232.36:8800"  # 看專案開誰的

PING_PATH = "/api/device/ping/"
PULL_PATH = "/device_pull"
ACK_PATH = "/device_ack"


def ping():
    # url = f"{API_BASE}/api/device/ping/"
    url = f"{API_BASE}{PING_PATH}"
    try:
        r = requests.post(
            url, json={"serial_number": SERIAL, "token": TOKEN}, timeout=5
        )
        r.raise_for_status()
        print("ping ok:", r.json())
        return True
    except Exception as e:
        print("ping err:", e)
        return False


def pull(max_wait=20):
    url = f"{API_BASE}/device_pull"
    try:
        r = requests.post(
            url,
            json={"serial_number": SERIAL, "token": TOKEN, "max_wait": max_wait},
            timeout=max_wait + 5,
        )
        if r.status_code == 204:
            return None
        r.raise_for_status()
        data = r.json()
        print("pull got:", data)
        return data
    except Exception as e:
        print("pull err:", e)
        return None


def ack(req_id, ok=True, error=""):
    url = f"{API_BASE}/device_ack"
    try:
        r = requests.post(
            url,
            json={
                "serial_number": SERIAL,
                "token": TOKEN,
                "req_id": req_id,
                "ok": ok,
                "error": error,
            },
            timeout=5,
        )
        r.raise_for_status()
        print("ack sent")
    except Exception as e:
        print("ack err:", e)


def unlock_hw():
    # TODO: GPIO 控制
    print("[HW] unlock pulse")
    time.sleep(0.2)


def main():
    last_ping = 0
    while True:
        # 每 30 秒 ping 一次
        if time.time() - last_ping > 30:
            ping()
            last_ping = time.time()

        # 拉指令
        cmd = pull(max_wait=20)
        if not cmd:
            continue

        if cmd.get("cmd") == "unlock":
            req_id = cmd.get("req_id")
            try:
                unlock_hw()
                ack(req_id, ok=True)
            except Exception as e:
                ack(req_id, ok=False, error=str(e))


if __name__ == "__main__":
    main()
```

# 樹莓派安裝 ZeroTier 與設定流程

本文整理如何在樹莓派 (Raspberry Pi) 上安裝 ZeroTier，並設定為透過 ZeroTier 的虛擬網路 IP 與伺服器 (Django) 溝通。

---

## 1️⃣ 建立 ZeroTier 帳號與網路

1. 前往 [ZeroTier 官網](https://www.zerotier.com/) 註冊帳號。
2. 登入後進入 [my.zerotier.com](https://my.zerotier.com)。
3. 在 **Networks** 分頁點擊 **Create A Network** 建立新網路。
4. 取得你的 **Network ID**（類似 `8286AC0E47AF653F`）。

---

## 2️⃣ 在樹莓派安裝 ZeroTier

```bash
curl -s https://install.zerotier.com | sudo bash
```

安裝完成後，ZeroTier 會自動以服務 (`zerotier-one`) 的方式啟動。

---

## 3️⃣ 加入網路

使用剛剛建立的 **Network ID**：

```bash
sudo zerotier-cli join <YOUR_NETWORK_ID>
```

範例：

```bash
sudo zerotier-cli join 8286AC0E47AF653F
```

---

## 4️⃣ 在 ZeroTier 管理平台授權設備

1. 回到 [my.zerotier.com](https://my.zerotier.com)。
2. 進入你的網路 → **Members**。
3. 找到剛剛加入的樹莓派設備，勾選 **Auth** 以授權。

---

## 5️⃣ 確認網路狀態與 IP

在樹莓派上：

```bash
sudo zerotier-cli listnetworks
```

範例輸出：

```
200 listnetworks <nwid> <name> <mac> <status> <type> <dev> <ZT assigned ips>
200 listnetworks 8286ac0e47af653f pi network 3e:97:f9:cd:ea:2e OK PRIVATE feth3911 172.28.232.36/16
```

這代表樹莓派已獲得一個 ZeroTier IP，例如：`172.28.232.36`。

---

## 6️⃣ 測試連線

在同一個 ZeroTier 網路中的其他機器上，ping 樹莓派：

```bash
ping 172.28.232.36
```

如果能通，代表虛擬網路已經成功。

---

## 7️⃣ 修改 Agent 設定使用 ZeroTier IP

在樹莓派的 `http_agent.py` 中，把 `API_BASE` 改成 **伺服器 (Django) 的 ZeroTier IP**：

```python
API_BASE = "http://172.28.232.36:8800/pi_devices"
```

- `172.28.232.36`：Django 伺服器在 ZeroTier 網路中的 IP。
- `8800`：Django runserver 使用的 port。

---

✅ 這樣就能透過 ZeroTier 網路讓樹莓派與伺服器安全溝通。

## 5. 建立 systemd 服務

新增檔案：

```bash
sudo nano /etc/systemd/system/homepi-agent.service
```

內容：

```ini
[Unit]
Description=HomePi HTTP Agent
After=network-online.target zerotier-one.service
Wants=network-online.target zerotier-one.service

[Service]
User=<username>
WorkingDirectory=/home/<username>/pi_agent
ExecStart=/usr/bin/python3 /home/<username>/pi_agent/http_agent.py
Restart=always

[Install]
WantedBy=multi-user.target
```

⚠️ 請依實際帳號修改 `User=` 與 `WorkingDirectory=`。

---

## 6. 啟動與管理

啟動並加入開機啟動：

```bash
sudo systemctl daemon-reload
sudo systemctl enable homepi-agent
sudo systemctl start homepi-agent
```

查看狀態：

```bash
sudo systemctl status homepi-agent --no-pager
```

追即時日誌：

```bash
journalctl -u homepi-agent -f
```

---

## 7. 更新程式碼

若修改了 `http_agent.py`：

```bash
sudo systemctl restart homepi-agent
```

---

## 8. 常見問題

- **狀態 217/USER**：User 與檔案目錄權限不符，請確認：
  ```bash
  sudo chown -R qkauia:qkauia /home/qkauia/pi_agent
  ```
- **未啟動成功**：改完 service 檔需 `sudo systemctl daemon-reload`。
- **無法連線**：請確認 Server 的 Django 是 `0.0.0.0:8800` 監聽，且用 ZeroTier IP 連線。

---

## 總整理：

# Mac + 樹莓派 ZeroTier 連線測試流程

本文件說明如何在 **Mac 與 Raspberry Pi** 上，透過 **ZeroTier** 建立虛擬網路並互相連線。

---

## 1. 安裝 ZeroTier

### Raspberry Pi

```bash
curl -s https://install.zerotier.com | sudo bash
sudo zerotier-cli join <你的-network-id>
```

### Mac

前往 [ZeroTier 官網](https://www.zerotier.com/download/) 下載 Mac 客戶端並安裝。  
安裝完成後，打開終端機，加入相同的網路：

```bash
zerotier-cli join <你的-network-id>
```

---

## 2. 在 ZeroTier Central 授權節點

1. 登入 [ZeroTier Central](https://my.zerotier.com)。
2. 打開對應的 Network。
3. 找到你的 Mac 和 Raspberry Pi 的節點，勾選 **Auth** 授權。

---

## 3. 確認虛擬 IP

在 Mac 和 Pi 上各自執行：

```bash
zerotier-cli listnetworks
```

會看到類似輸出：

- Mac: `172.28.231.139/16`
- Raspberry Pi: `172.28.232.36/16`

---

## 4. 測試連線

### 從 Mac ping Pi

```bash
ping 172.28.232.36
```

### 從 Pi ping Mac

```bash
ping 172.28.231.139
```

若能互通，代表 ZeroTier 網路已成功建立。

---

## 5. 應用服務測試

例如，若 Django server 在 Mac 上執行 8800 port，  
樹莓派可以用虛擬 IP 存取：

```bash
curl -X POST http://172.28.231.139:8800/api/device/ping/   -H "Content-Type: application/json"   -d '{"serial_number":"<PI-SERIAL>","token":"<DEVICE-TOKEN>"}'
```

---

✅ 這樣不論 Mac 與樹莓派是否在同一實體網路，都能透過 ZeroTier 虛擬 LAN 溝通。

### 觀看樹梅派 ZeroTier 的 IP 位置 指令：

- `sudo zerotier-cli listnetworks`
