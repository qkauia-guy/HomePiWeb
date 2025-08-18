from django.urls import path
from . import views

urlpatterns = [
    path("", views.notifications_list, name="notifications_list"),
    path("read-all/", views.notifications_read_all, name="notifications_read_all"),
    path("<int:pk>/read/", views.notification_read, name="notification_read"),
    path("<int:pk>/go/", views.notification_go, name="notifications_detail_redirect"),
]
