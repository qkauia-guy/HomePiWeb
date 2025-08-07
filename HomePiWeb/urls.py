from django.contrib import admin
from django.urls import path
from users import views
from users.views import login_view, home_view


urlpatterns = [
    path("admin/", admin.site.urls),  # Django 後台
    path("register/", views.register_view, name="register"),  # 註冊
    path("login/", login_view, name="login"),
    path("home/", home_view, name="home"),
]
