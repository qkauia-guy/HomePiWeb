<!-- markdownlint-disable -->

##### 下載專案 / 建立虛擬機 / 建立新裝置 / 綁定裝置註冊會員

1. Github clone 下載專案(確認最新分支)
2. **windows** 開啟 `Anaconda Powershell`
3. `cd 專案目錄`
4. `conda env create -f environment_windows.yml` ( mac 使用者 使用`environment.yml` )
   > Conda 需要在 environment.yml 檔案所在的目錄中才能讀取它。
5. `conda env list` 確認有沒有建立成功 HomePiWeb 虛擬環境
6. `conda activate HomePiWeb`
7.

```bash
python manage.py makemigrations
python manage.py migrate
```

8. `python manage.py shell`
9. **裝置序號 和 裝置 token 要記下來備用**

```python
from pi_devices.models import Device
# 建立一筆新裝置
d = Device.objects.create()

print(d.serial_number)      # 系統自動產生的序號
print(d.token)              # 自動產生的 Token

#print(d.verification_code)  # 自動產生的驗證碼
#print(d.id)                 # 新增後的 ID

# 進行轉換成註冊頁面QR CODE png
from pi_devices.utils.qrcode_utils import generate_device_qrcode
file_path = generate_device_qrcode(d)
print("QR Code 已儲存於：", file_path)
```

10. 進行註冊和綁定裝置 (掃 QRCODE)

---

##### 樹梅派初始設定 ( ping 本地專案 )

1. `cd /home/<username>`
   > 必須在使用者目錄下，以免後續權限問題
2. `mkdir pi_agent`
3. `cd pi_agent`
4. `sudo nano http_agent.py` ( 複製`http_agent.py` 的 code, **裝置序號**,**裝置 token** 使用之前綁定的裝置 )

5. `sudo nano /etc/systemd/system/homepi-agent.service` ( 複製`homepi-agent.service`的 code,使用者名稱必須替換 )
   > .service 檔案需要以 root 權限在 /etc/systemd/system/ 目錄下建立。
6.

```bash
# * 停掉 systemd 的 agent
sudo systemctl stop homepi-agent

# * 重新載入設定
sudo systemctl daemon-reload

# * 重 / 啟動 systemd 的 agent
sudo systemctl restart homepi-agent
sudo systemctl start homepi-agent

# * 啟用 homepi-agent 服務，讓它在每次開機時都會自動啟動。
sudo systemctl enable homepi-agent

# 下面為測試用：
# 以 service 同一個帳號手動跑（以下假設 User=qkauia）
sudo -u <username> PYTHONUNBUFFERED=1 GPIOZERO_PIN_FACTORY=rpigpio \
  LED_ACTIVE_HIGH=true LED_PIN=17 \
  python3 /home/<username>/pi_agent/http_agent.py
# 檢查 journal 是否有 GPIO 初始化警告
journalctl -u homepi-agent -b --no-pager | grep -i gpio -n
# 查看 homepi-agent 服務的當前狀態
sudo systemctl status homepi-agent --no-pager
# 查詢與顯示 systemd 日誌的工具
journalctl -u homepi-agent -f
```

> 輸入初始化警告指令,如果看到類似：`[WARN] gpiozero LED init failed: ...` 就確定是 systemd 環境下的 GPIO 初始化失敗。

7. 安裝套件( 目前 IOT 有使用到 )

```bash
sudo apt-get install -y python3-gpiozero python3-lgpio`
# 安裝 Python 3 的 smbus 函式庫
sudo apt-get install python3-smbus
# 安裝 I2C 偵測工具
sudo apt-get install i2c-tools
# 使用 pip 安裝 smbus2 模組
pip3 install smbus2
```

##### 權限設定

```bash
# 改變一個檔案或目錄的所有權
sudo chown -R <username>:<username> /home/<username>/pi_agent
#
sudo adduser <username> dialout
# 加入 gpio 群組
sudo adduser <username> gpio
```

> dialout 群組是 Linux 系統中一個常見的特殊群組，其主要作用是讓使用者能夠存取串列埠（Serial Port）和數據機（Modem）。
> dialout 群組賦予使用者存取串列埠（如 /dev/ttyS0、/dev/ttyUSB0）的權限。這對於與樹莓派的 GPIO 腳位或外部硬體（如 Arduino）通訊非常重要，因為這些通訊通常會透過串列埠進行。

> gpio 群組賦予使用者直接控制樹莓派 GPIO 腳位的權限。許多 Python GPIO 函式庫，如 gpiozero 和 RPi.GPIO，都需要使用者屬於這個群組才能正常操作 GPIO 腳位。

##### 樹莓派安裝 ZeroTier 與設定流程

1.

```bash
# 在樹莓派安裝 ZeroTier
curl -s https://install.zerotier.com | sudo bash
```

```bash
sudo zerotier-cli join <YOUR_NETWORK_ID>
```

範例：

```bash
sudo zerotier-cli join 8286AC0E47AF653F
```

##### 在 ZeroTier 管理平台授權設備

1. 回到 [my.zerotier.com](https://my.zerotier.com)。
2. 進入你的網路 → **Members**。
3. 找到剛剛加入的樹莓派設備，勾選 **Auth** 以授權。
4. 在**樹莓派**確認網路狀態與 IP

：

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

##### 測試連線

在同一個 ZeroTier 網路中的其他機器上，ping 樹莓派：

```bash
ping 172.28.232.36
```

如果能通，代表虛擬網路已經成功。這樣就能透過 ZeroTier 網路讓樹莓派與伺服器安全溝通。

##### IoT 擴充檔案分層設定

```bash
pi_agent/
├── http_agent.py          # 主程式（專心分發命令）
├── devices/
│   ├── __init__.py
│   └── led.py             # LED 控制模組
└── utils/
    ├── __init__.py
    └── http.py            # HTTP 工具（ping/pull/ack）
```

##### 指令透過 ssh 移動整個目錄：

```bash
rsync -avz ~/<自己本地的路徑>/HomePiWeb/pi_agent/ <Hostname>:/home/<pi5UserName>/pi_agent/
```

示範：

```bash
rsync -avz ~/Desktop/HomePiWeb/pi_agent/ qkauia.pie:/home/qkauia/pi_agent/
```

修改 `http.py`
