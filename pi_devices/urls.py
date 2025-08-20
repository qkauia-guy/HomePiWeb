from django.urls import path
from .views import device_ping
from . import views as device_views
from . import views

urlpatterns = [
    path("my-devices/", device_views.my_devices, name="my_devices"),
    path("devices/bind/", device_views.device_bind, name="device_bind"),
    path("devices/<int:pk>/unbind/", device_views.device_unbind, name="device_unbind"),
    path(
        "devices/<int:pk>/edit/", device_views.device_edit_name, name="device_edit_name"
    ),
    path("api/device/ping/", device_ping, name="device_ping"),
    # 使用者下指令（需要登入）
    path(
        "api/devices/<int:device_id>/unlock/", views.unlock_device, name="unlock_device"
    ),
    # 裝置端長輪詢 & 回報（無需 CSRF，使用 serial_number + token 驗證）
    path("device_pull", views.device_pull, name="device_pull"),
    path("device_ack", views.device_ack, name="device_ack"),
    path(
        "api/devices/<int:device_id>/unlock/", views.unlock_device, name="unlock_device"
    ),
    path(
        "api/devices/<int:device_id>/light/<str:action>/",
        views.device_light_action,
        name="device_light_action",
    ),
]
