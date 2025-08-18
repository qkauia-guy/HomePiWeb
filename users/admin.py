from django.contrib import admin
from django.contrib.auth.admin import (
    UserAdmin as BaseUserAdmin,
)  # 匯入 Django 內建的 UserAdmin 以方便擴充
from .models import User  # 匯入你自訂的 User 模型
from .forms import (
    UserRegisterForm,
)  # 匯入自訂的註冊表單（通常用於建立新使用者時的密碼驗證等）


# 自訂 UserAdmin 繼承自 Django 預設 UserAdmin，用來管理自訂 User 在 admin 後台的顯示與操作行為
class UserAdmin(BaseUserAdmin):

    # 指定在 Django admin 新增使用者時，使用自訂的表單類別（含密碼驗證）
    add_form = UserRegisterForm

    # 設定在 admin 「使用者列表頁」中顯示的欄位 (email, role, is_staff)
    list_display = ("email", "role", "is_staff", "id")

    # 排序方式，根據 email 欄位排序使用者列表
    ordering = ("email",)

    # 搜尋框允許根據 email 進行搜尋
    search_fields = ("email",)

    # 使用者詳細頁（修改頁面）中分區顯示的欄位群組
    fieldsets = (
        (
            None,
            {"fields": ("email", "password", "role")},
        ),  # 第一區：帳號基本資訊與密碼與角色
        (
            "Permissions",
            {"fields": ("is_staff", "is_superuser")},
        ),  # 第二區：權限相關設定
    )

    # 新增使用者頁面中欄位分組設定，與表單份額
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),  # admin 頁面 CSS 類別名，讓欄位寬度較寬
                "fields": (
                    "email",
                    "role",
                    "password1",
                    "password2",
                ),  # 新增時填寫的欄位 (email、角色和兩次輸入密碼)
            },
        ),
    )


# 將自訂 User 模型註冊到 Django admin，並用剛剛定義的 UserAdmin 來管理
admin.site.register(User, UserAdmin)
