# pi_devices/views/__init__.py
from . import device, capability, api

# 轉出口給舊匯入寫法用
from .api import device_ping, device_pull, device_ack

__all__ = [
    "device",
    "capability",
    "api",
    "device_ping",
    "device_pull",
    "device_ack",
]
