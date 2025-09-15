import psutil
import subprocess


def get_pi_metrics():
    metrics = {}
    try:
        # CPU / Mem
        metrics["cpu_percent"] = psutil.cpu_percent(interval=0.5)
        metrics["memory_percent"] = psutil.virtual_memory().percent

        # 溫度：先試 vcgencmd，再 fallback
        temp = None
        try:
            output = subprocess.check_output(
                ["vcgencmd", "measure_temp"], encoding="utf-8"
            )
            temp = float(output.replace("temp=", "").replace("'C", "").strip())
        except Exception:
            try:
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    milli = int(f.read().strip())
                temp = milli / 1000.0
            except Exception:
                temps = psutil.sensors_temperatures()
                if "cpu-thermal" in temps:
                    temp = temps["cpu-thermal"][0].current

        if temp is not None:
            metrics["temperature"] = temp

    except Exception as e:
        print(f"[WARN] get_pi_metrics failed: {e}")

    return metrics
