# groups/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # CRUD
    path("", views.group_list, name="group_list"),
    path("create/", views.group_create, name="group_create"),
    path("<int:group_id>/edit/", views.group_update, name="group_update"),
    path("<int:group_id>/delete/", views.group_delete, name="group_delete"),
    path("<int:group_id>/", views.group_detail, name="group_detail"),
    # 成員管理
    path("<int:group_id>/members/", views.group_members, name="group_members"),
    path(
        "<int:group_id>/members/<int:membership_id>/set-role/",
        views.member_set_role,
        name="member_set_role",
    ),
    path(
        "<int:group_id>/members/<int:membership_id>/remove/",
        views.member_remove,
        name="member_remove",
    ),
    # 裝置掛入/移除
    path(
        "<int:group_id>/attach/<int:device_id>/",
        views.attach_device,
        name="group_attach_device",
    ),
    path(
        "<int:group_id>/detach/<int:device_id>/",
        views.detach_device,
        name="group_detach_device",
    ),
    # 成員裝置分享申請 & 審核
    path(
        "<int:group_id>/devices/<int:device_id>/request-share/",
        views.request_share_device,
        name="request_share_device",
    ),
    path(
        "<int:group_id>/requests/<int:req_id>/review/",
        views.review_share_request,
        name="review_share_request",
    ),
    # 管理員持續性授權管理
    path(
        "<int:group_id>/grants/<int:user_id>/grant/",
        views.grant_share_permission,
        name="grant_share_permission",
    ),
    path(
        "<int:group_id>/grants/<int:user_id>/revoke/",
        views.revoke_share_permission,
        name="revoke_share_permission",
    ),
]
