from django.urls import path
from .views import device_ping
from . import views as device_views

urlpatterns = [
    path("my-devices/", device_views.my_devices, name="my_devices"),
    path("devices/bind/", device_views.device_bind, name="device_bind"),
    path("devices/<int:pk>/unbind/", device_views.device_unbind, name="device_unbind"),
    path(
        "devices/<int:pk>/edit/", device_views.device_edit_name, name="device_edit_name"
    ),
    path("api/device/ping/", device_ping, name="device_ping"),
]
