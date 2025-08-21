# HomePiWeb/middleware.py
from django.urls import resolve, reverse, Resolver404, NoReverseMatch
from django.shortcuts import redirect
from django.contrib import messages
from groups.models import Group, GroupMembership
from django.http import JsonResponse


EXEMPT_URL_NAMES = {
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
}
EXEMPT_PATH_PREFIXES = ("/admin/", "/static/", "/media/", "/favicon.ico", "/invites/")


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
        if not request.user.is_authenticated:
            return self.get_response(request)

        path = request.path
        if any(path.startswith(p) for p in EXEMPT_PATH_PREFIXES):
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

        if view_name in EXEMPT_URL_NAMES:
            return self.get_response(request)

        if not user_has_any_group(request.user):
            # ✅ XHR 回 403 JSON
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"error": "group_required", "redirect": _group_create_url()},
                    status=403,
                )
            messages.warning(request, "你尚未加入任何群組，請先建立群組才能繼續操作。")
            return redirect(_group_create_url())

        # ✅ 別忘了：有群組時要放行
        return self.get_response(request)
