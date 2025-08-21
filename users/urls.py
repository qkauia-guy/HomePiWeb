from django.urls import path
from .views import register_view, login_view, logout_view, home_view
from .views_password_reset import (
    password_reset_request_view,
    password_reset_confirm_view,
)
from . import views

urlpatterns = [
    path("register/", register_view, name="register"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("home/", home_view, name="home"),
    # 忘記密碼（可切換不寄信 / 寄信）
    path("password_reset/", password_reset_request_view, name="password_reset_request"),
    path(
        "reset/<uidb64>/<token>/",
        password_reset_confirm_view,
        name="password_reset_confirm_custom",
    ),
    # 三個 AJAX 端點（lazy load partial）
    path("controls/devices/", views.ajax_devices, name="ajax_devices"),
    path("controls/caps/", views.ajax_caps, name="ajax_caps"),
    path("controls/cap-form/<int:cap_id>/", views.ajax_cap_form, name="ajax_cap_form"),
]
