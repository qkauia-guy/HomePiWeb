# pi_devices/urls.py
from django.urls import path
from .views import device as device_views
from .views import api as api_views
from .views import capability as capability_views

urlpatterns = [
    # 使用者側（Device）
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
    # Capability actions —— 統一指向 capability_views.capability_action
    # Canonical（新）
    path(
        "devices/<int:device_id>/caps/<int:cap_id>/<str:action>/",
        capability_views.capability_action,
        name="capability_action",
    ),
    # Legacy（舊樣式也一起導到同一支，避免混用造成行為差異）
    path(
        "devices/<int:device_id>/cap/<int:cap_id>/action/<str:action>/",
        capability_views.capability_action,
        name="capability_action_legacy",
    ),
    # Pi Agent API（給樹莓派）—— 你的 api.py 已 @csrf_exempt，這裡不用再包一層
    path("api/device/ping/", api_views.device_ping, name="device_ping"),
    path("api/device/pull/", api_views.device_pull, name="device_pull_api"),
    path("api/device/ack/", api_views.device_ack, name="device_ack_api"),
    # 面板狀態連動
    path(
        "api/device/<int:device_id>/status/", api_views.api_device_status, name="api_device_status"
    ),
    path(
        "api/cap/<int:cap_id>/status/", api_views.api_cap_status, name="api_cap_status"
    ),
    # 若你有既有 agent 用到無斜線版本，保留兼容
    path("device_pull/", api_views.device_pull, name="device_pull"),
    # path("device_pull", api_views.device_pull),
    path("device_ack/", api_views.device_ack, name="device_ack"),
    # Camera 控制/查詢
    path(
        "devices/<str:serial>/camera/<str:action>/",
        api_views.camera_action,
        name="camera_action",
    ),
    path(
        "devices/<str:serial>/camera/status/",
        api_views.camera_status,
        name="camera_status",
    ),
    # 直播新視窗頁
    path(
        "live/<int:device_id>/<int:cap_id>/",
        capability_views.live_player,
        name="cap_live_player",
    ),
    path("api/device/schedules/", api_views.device_schedules, name="device_schedules"),
    path(
        "api/device/schedule_ack/",
        api_views.device_schedule_ack,
        name="device_schedule_ack",
    ),
    path("schedules/create/", device_views.create_schedule, name="create_schedule"),
    path("remove_schedule/", device_views.remove_schedule, name="remove_schedule"),
    path(
        "api/device/<int:device_id>/schedules/",
        device_views.upcoming_schedules,
        name="upcoming_schedules",
    ),
    path("api/device/<int:device_id>/logs/", api_views.device_logs, name="device_logs"),
    path(
        "device/<int:pk>/",
        device_views.DeviceDetailView.as_view(),
        name="device_detail",
    ),
]
