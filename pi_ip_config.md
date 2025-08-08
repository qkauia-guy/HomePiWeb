# /home/qkauia/pi_ping.py

import time
import requests
import socket

DJANGO_SERVER = "http://192.168.0.100:8800" # ✅ 修改成你的 Django 伺服器 IP
DEVICE_SERIAL = "PI-AD3F44FC" # ✅ 改成設備序號，或用 socket.gethostname()

def get_device_serial():
return socket.gethostname() # 或從其他方式獲得唯一序號

def ping():
url = f"{DJANGO_SERVER}/api/device/ping/"
payload = {
"serial_number": get_device_serial()
}
try:
response = requests.post(url, json=payload, timeout=5)
print(f"✅ Ping sent. Status: {response.status_code}, Response: {response.json()}")
except Exception as e:
print("❌ Ping failed:", e)

if **name** == "**main**":
while True:
ping()
time.sleep(60) # 每 60 秒 Ping 一次

curl -X POST http://192.168.0.100:8800/api/ping/ \
 -H "Content-Type: application/json" \
 -d '{"serial_number": "PI-AD3F44FC"}'

from pi_devices.models import Device
from pi_devices.utils.qrcode_utils import generate_device_qrcode
device = Device.objects.create()
file_path = generate_device_qrcode(device)
print("QR Code 已儲存於：", file_path)

from pi_devices.models import Device
from django.utils import timezone
Device.objects.get(serial_number="PI-AD3F44FC").last_ping
d = Device.objects.get(serial_number="PI-AD3F44FC")
print(d.last_ping)

  <script>
  document.addEventListener("DOMContentLoaded", function () {
    const serial = "{{ request.user.device.serial_number|default:'' }}";
    if (serial) {
      fetch("/api/device/ping/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ serial_number: serial }),
      })
      .then((res) => res.json())
      .then((data) => {
        console.log("設備狀態：", data);
      })
      .catch((err) => console.error("Ping 失敗", err));
    }
  });
</script>
