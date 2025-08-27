# HomePiWeb/urls.py
from django.contrib import admin
from django.urls import path, re_path, include
from django.shortcuts import redirect
from django.http import HttpResponse

from users import views as user_views
from pi_devices.views import device as device_views
from pi_devices.views import api as api_views


def index_or_health(request):
    if request.user.is_authenticated:
        return redirect("home")
    # 未登入時回 200 OK，避免誤打根目錄時跳轉到 /login/
    return HttpResponse("OK", content_type="text/plain", status=200)


urlpatterns = [
    # HLS 代理
    re_path(
        r"^hls/(?P<serial>[^/]+)/(?P<subpath>.+)$",
        api_views.hls_proxy,
        name="hls_proxy",
    ),
    path("admin/", admin.site.urls),
    # 使用者/裝置/群組/邀請
    path("", include("users.urls")),
    path("", include("pi_devices.urls")),
    path("groups/", include("groups.urls")),
    path("invites/", include("invites.urls")),
    # 通知（HTML 與 API）
    path("notifications/", include("notifications.web_urls")),
    path("api/", include("notifications.api_urls")),
    # IoT Agent API（同時支援有/無斜線）
    path("device_ping", api_views.device_ping),
    path("device_ping/", api_views.device_ping, name="device_ping"),
    path("device_pull", api_views.device_pull),
    path("device_pull/", api_views.device_pull, name="device_pull"),
    path("device_ack", api_views.device_ack),
    path("device_ack/", api_views.device_ack, name="device_ack"),
    # Camera 控制/查詢（可保留）
    path(
        "api/camera/<str:serial>/<str:action>/",
        api_views.camera_action,
        name="camera_action",
    ),
    path(
        "api/camera/<str:serial>/status/", api_views.camera_status, name="camera_status"
    ),
    # Offcanvas
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
