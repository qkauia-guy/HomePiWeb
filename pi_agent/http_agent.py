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
