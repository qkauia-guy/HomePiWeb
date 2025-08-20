# pi_devices/migrations/000X_backfill_default_light.py

from django.db import migrations


def backfill_default_light(apps, schema_editor):
    """
    此函數用於回填預設的燈光能力。
    它會遍歷所有裝置，如果某個裝置沒有任何能力，
    就會為其創建一個預設的燈光能力。
    """
    # 取得歷史版本的模型，這是資料遷移的最佳實踐
    Device = apps.get_model("pi_devices", "Device")
    DeviceCapability = apps.get_model("pi_devices", "DeviceCapability")

    for dev in Device.objects.all():
        # 若該裝置尚無任何能力，幫他建一個預設燈光
        if not DeviceCapability.objects.filter(device=dev).exists():
            DeviceCapability.objects.create(
                device=dev,
                kind="light",
                name="燈光1",
                slug="light-1",
                config={"pin": 17, "active_high": True},
                order=0,
            )


class Migration(migrations.Migration):

    dependencies = [
        # 替換為你的最新遷移檔名稱
        ("pi_devices", "0011_devicecapability"),
    ]

    operations = [
        # 運行 Python 程式碼來執行資料回填
        migrations.RunPython(backfill_default_light, migrations.RunPython.noop),
    ]
