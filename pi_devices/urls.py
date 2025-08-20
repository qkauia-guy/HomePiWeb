# pi_devices/urls.py
from django.urls import path
from .views import device as device_views
from .views import api as api_views
from .views import (
    capability as cap_views,
)  # 若尚未啟用 Capability，可先註解掉這行與下方4條路由
from django.views.decorators.csrf import csrf_exempt


urlpatterns = [
    # 使用者側（Device）
    path("my-devices/", device_views.my_devices, name="my_devices"),
    path("devices/bind/", device_views.device_bind, name="device_bind"),
    path("devices/<int:pk>/unbind/", device_views.device_unbind, name="device_unbind"),
    path("devices/<int:pk>/edit/", device_views.device_edit, name="device_edit"),
    path(
        "devices/<int:device_id>/unlock/",
        device_views.unlock_device,
        name="unlock_device",
    ),
    path(
        "devices/<int:device_id>/light/<slug:action>/",
        device_views.device_light_action,
        name="device_light_action",
    ),
    path(
        "devices/<int:device_id>/cap/<int:cap_id>/action/<slug:action>/",
        cap_views.action,
        name="capability_action",
    ),
    # Pi Agent API（給樹莓派）
    path("api/device/ping/", csrf_exempt(api_views.device_ping), name="device_ping"),
    path("device_pull", csrf_exempt(api_views.device_pull), name="device_pull"),
    path("device_ack", csrf_exempt(api_views.device_ack), name="device_ack"),
]
