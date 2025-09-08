# HomePiWeb/middleware.py
from django.urls import resolve, reverse, Resolver404, NoReverseMatch
from django.shortcuts import redirect
from django.contrib import messages
from groups.models import Group, GroupMembership
from django.http import JsonResponse

EXEMPT_URL_NAMES = {
    "hls_proxy",
    "login",
    "logout",
    "users:login",
    "users:logout",
    "register",
    "users:register",
    "password_reset_request",
    "password_reset_confirm",
    "password_reset_complete",
    "password_reset_done",
    "group_create",
    "groups:group_create",
    "admin:index",
    "device_ping",
    "device_pull",
    "device_ack",
}

EXEMPT_PATH_PREFIXES = (
    "/hls/",
    "/admin/",
    "/static/",
    "/media/",
    "/favicon.ico",
    "/invites/",
    "/api/device/",
    "/device_ping",
    "/device_pull",
    "/device_ack",
)


def user_has_any_group(user) -> bool:
    return (
        Group.objects.filter(owner=user).exists()
        or GroupMembership.objects.filter(user=user).exists()
    )


def _group_create_url():
    try:
        return reverse("groups:group_create")
    except NoReverseMatch:
        return reverse("group_create")


class RequireGroupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # ✅ 無條件放行：HLS 代理 & Pi Agent API & 靜態檔
        if (
            path.startswith("/hls/")
            or path.startswith("/api/device/")
            or path.startswith("/device_pull/")
            or path.startswith("/device_ack")
            or path.startswith("/static/")
            or path.startswith("/media/")
            or path.startswith("/favicon.ico")
            or path.startswith("/admin/")
        ):
            return self.get_response(request)

        # 其餘才走原本流程
        if not request.user.is_authenticated:
            return self.get_response(request)

        try:
            match = resolve(path)
            view_name = (
                f"{match.namespace}:{match.url_name}"
                if match.namespace
                else match.url_name
            )
        except Resolver404:
            return self.get_response(request)

        # ✅ 放行白名單的 view 名稱
        if view_name in EXEMPT_URL_NAMES:
            return self.get_response(request)

        # 沒加入任何群組 → 擋住
        if not user_has_any_group(request.user):
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"error": "group_required", "redirect": _group_create_url()},
                    status=403,
                )
            messages.warning(request, "你尚未加入任何群組，請先建立群組才能繼續操作。")
            return redirect(_group_create_url())

        return self.get_response(request)
