from django.urls import path
from .views import device_ping

urlpatterns = [
    path("api/device/ping/", device_ping, name="device_ping"),
]
