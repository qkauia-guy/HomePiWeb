from django.contrib import admin
from django.urls import path, re_path, include
from django.shortcuts import redirect
from django.http import HttpResponse

from users import views as user_views
from pi_devices.views import device as device_views
from pi_devices.views import api as api_views


def index_or_health(request):
    # 已登入 → 導到首頁
    if request.user.is_authenticated:
        return redirect("home")
    return redirect("login")


urlpatterns = [
    # HLS 代理
    re_path(
        r"^hls/(?P<serial>[^/]+)/(?P<subpath>.+)$",
        api_views.hls_proxy,
        name="hls_proxy",
    ),
    # Django admin
    path("admin/", admin.site.urls),
    # 使用者/裝置/群組/邀請
    path("", include("users.urls")),
    path("", include("pi_devices.urls")),
    path("groups/", include("groups.urls")),
    path("invites/", include("invites.urls")),
    # 通知（HTML 與 API）
    path("notifications/", include("notifications.web_urls")),
    path("api/", include("notifications.api_urls")),
    # === IoT Agent API（新版，與樹莓派一致） ===
    path("api/device/ping/", api_views.device_ping, name="api_device_ping"),
    path("api/device/pull/", api_views.device_pull, name="api_device_pull"),
    path("api/device/ack/", api_views.device_ack, name="api_device_ack"),
    path(
        "api/device/schedules/", api_views.device_schedules, name="api_device_schedules"
    ),
    path(
        "api/device/schedule_ack/",
        api_views.device_schedule_ack,
        name="api_device_schedule_ack",
    ),
    # Camera 控制/查詢
    path(
        "api/camera/<str:serial>/<str:action>/",
        api_views.camera_action,
        name="camera_action",
    ),
    path(
        "api/camera/<str:serial>/status/",
        api_views.camera_status,
        name="camera_status",
    ),
    # Offcanvas 側邊欄
    path("devices/offcanvas/", device_views.offcanvas_list, name="devices_offcanvas"),
    path("offcanvas/groups/", user_views.offcanvas_groups, name="groups_offcanvas"),
    # 健康檢查 & 首頁
    path(
        "healthz",
        lambda r: HttpResponse("OK", content_type="text/plain"),
        name="healthz",
    ),
    path("", index_or_health, name="index"),
]
