from django.urls import path
from . import views

urlpatterns = [
    path(
        "group/<int:group_id>/", views.invitation_list, name="invite_list"
    ),  # ← 新增：列表
    path(
        "revoke/<str:code>/", views.revoke_invitation, name="invite_revoke"
    ),  # ← 新增：撤銷
    path(
        "create/<int:group_id>/<int:device_id>/",
        views.create_invitation,
        name="invite_create",
    ),
    path("accept/<str:code>/", views.accept_invite, name="invite_accept"),
    path("revoke/<str:code>/", views.revoke_invitation, name="invite_revoke"),
]
