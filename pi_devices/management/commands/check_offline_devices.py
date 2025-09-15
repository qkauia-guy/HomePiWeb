from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

from pi_devices.models import Device
from HomePiWeb.mongo import device_ping_logs


class Command(BaseCommand):
    help = "檢查裝置是否掉線，並補一筆 offline 紀錄到 MongoDB"

    def handle(self, *args, **options):
        window = getattr(settings, "DEVICE_ONLINE_WINDOW_SECONDS", 60)
        threshold = timezone.now() - timedelta(seconds=window)

        devices = Device.objects.all()
        offline_count = 0

        for device in devices:
            if not device.last_ping or device.last_ping < threshold:
                # 查 MongoDB 最後一筆紀錄
                last_log = (
                    device_ping_logs.find({"device_id": device.serial_number})
                    .sort("ping_at", -1)
                    .limit(1)
                )
                last_log = list(last_log)
                if last_log and last_log[0].get("status") == "offline":
                    continue  # 已經有 offline 紀錄，就不要再補

                # 補一筆 offline 紀錄
                device_ping_logs.insert_one(
                    {
                        "device_id": device.serial_number,
                        "ping_at": timezone.now().utcnow(),  # 紀錄掉線時間
                        "status": "offline",
                    }
                )
                offline_count += 1

        self.stdout.write(self.style.SUCCESS(f"補了 {offline_count} 筆 offline 紀錄"))
