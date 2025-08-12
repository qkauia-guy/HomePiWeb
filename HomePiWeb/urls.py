from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

urlpatterns = [
    path("admin/", admin.site.urls),
    # 使用者相關路由（register/login/home + 密碼重設）
    path("", include("users.urls")),
    path("", include("pi_devices.urls")),
    path("groups/", include("groups.urls")),
    path(
        "",
        lambda request: (
            redirect("home") if request.user.is_authenticated else redirect("login")
        ),
        name="index",
    ),
]
