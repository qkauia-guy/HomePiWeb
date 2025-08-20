<!-- markdownlint-disable -->

```python
[Unit]
Description=HomePi HTTP Agent              # 服務描述，顯示在 systemctl status
After=network-online.target                # 等「網路就緒」之後再啟動（避免一啟動就打 API 失敗）
Wants=network-online.target                # 希望同時把 network-online.target 拉起來（非硬性依賴）

# 若你的網路用的是 systemd-networkd，可加：
# After=systemd-networkd-wait-online.service
# Wants=systemd-networkd-wait-online.service
# 若是 NetworkManager，可改用：
# After=NetworkManager-wait-online.service
# Wants=NetworkManager-wait-online.service
# 若依賴 Zerotier：可加（視是否一定要 Zerotier 才能打 API）
# After=zerotier-one.service
# Wants=zerotier-one.service

[Service]
Type=simple                                # 前景常駐程式（預設），python 腳本適用
User=<username>                            # 以哪個使用者身份跑（⚠️ 改成實際帳號）
WorkingDirectory=/home/<username>/pi_agent # 工作目錄（⚠️ 與 User 家目錄一致、且檔案存在）

# 主程式啟動命令（建議絕對路徑）
# - 若使用 venv，改成 ExecStart=/home/<username>/.venv/bin/python /home/<username>/pi_agent/http_agent.py
ExecStart=/usr/bin/python3 /home/<username>/pi_agent/http_agent.py

# ======== 環境變數（給你的 Python 腳本用）========
Environment=PYTHONUNBUFFERED=1             # 讓 print 立即刷到 journal（不緩衝，方便即時看 log）
Environment=GPIOZERO_PIN_FACTORY=lgpio     # gpiozero 使用 lgpio 後端（Bookworm 推薦）
Environment=LED_PIN=17                     # 覆寫你的腳位（程式會讀取 os.getenv）
Environment=LED_ACTIVE_HIGH=true           # LED 高電位亮；接反就改 false/0/no

# 你也可以把頻繁變動的參數放到外部檔案：
# EnvironmentFile=/etc/default/homepi-agent
# 並在該檔案內寫：
#   SERIAL=PI-XXXXXXX
#   TOKEN=xxxxxxxx...
#   API_BASE=http://172.28.x.x:8800

# ======== 可靠性設定 ========
Restart=always                             # 程式崩潰或退出時自動重啟
RestartSec=3                               # 重啟前的間隔（秒）

# （可選）把 stdout/stderr 指定到 journal（預設就是 journal，可以省略）
# StandardOutput=journal
# StandardError=journal

# （可選）資安/隔離（按需開啟，開太兇可能影響存取 GPIO、檔案）
# NoNewPrivileges=true
# PrivateTmp=true
# ProtectSystem=full
# ProtectHome=read-only
# ReadWritePaths=/home/<username>/pi_agent

[Install]
WantedBy=multi-user.target                 # 多使用者（文字）模式進入時自動啟用
```
