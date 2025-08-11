# /Users/qkauia/Desktop/HomePiWeb/users/urls.py
from django.urls import path
from .views import register_view, login_view, logout_view, home_view
from .views_password_reset import (
    password_reset_request_view,
    password_reset_confirm_view,
)

urlpatterns = [
    path("register/", register_view, name="register"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("home/", home_view, name="home"),
    # 忘記密碼（可切換不寄信 / 寄信）
    path("password-reset/", password_reset_request_view, name="password_reset_request"),
    path(
        "reset/<uidb64>/<token>/",
        password_reset_confirm_view,
        name="password_reset_confirm_custom",
    ),
]
