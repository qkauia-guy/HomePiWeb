from django.contrib import admin
from django.contrib.auth.admin import (
    UserAdmin as BaseUserAdmin,
)  # 匯入 Django 內建的 UserAdmin 以方便擴充
from .models import User  # 匯入你自訂的 User 模型
from .forms import (
    UserRegisterForm,
)  # 匯入自訂的註冊表單（通常用於建立新使用者時的密碼驗證等）

# ===== 後台站名與標題（中文）=====
# 放在已註冊的 app 的 admin.py，確保會被 Django 自動載入
admin.site.site_header = "HomePi 後台管理"
admin.site.site_title = "HomePi 管理後台"
admin.site.index_title = "功能總覽"


# 自訂 UserAdmin 繼承自 Django 預設 UserAdmin，用來管理自訂 User 在 admin 後台的顯示與操作行為
class UserAdmin(BaseUserAdmin):

    # 指定在 Django admin 新增使用者時，使用自訂的表單類別（含密碼驗證）
    add_form = UserRegisterForm

    # 設定在 admin 「使用者列表頁」中顯示的欄位（中文）
    # 顯示：Email、角色、是否管理員/超管、是否啟用、建立時間、線上狀態徽章、ID
    list_display = (
        "col_email",
        "col_role",
        "col_is_staff",
        "col_is_superuser",
        "col_is_active",
        "col_date_joined",
        "online_badge",
        "col_id",
    )

    # 排序方式，根據 email 欄位排序使用者列表
    ordering = ("-date_joined", "email")

    # 搜尋框允許根據 email 進行搜尋
    search_fields = ("email",)

    # 右側過濾器：依角色、權限、啟用狀態過濾
    list_filter = ("role", "is_staff", "is_superuser", "is_active")

    # 使用者詳細頁（修改頁面）中分區顯示的欄位群組
    fieldsets = (
        (
            None,
            {"fields": ("email", "password", "role")},
        ),  # 第一區：帳號基本資訊與密碼與角色
        (
            "權限設定",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),  # 第二區：權限相關設定（中文）
        (
            "重要時間",
            {"fields": ("last_login", "date_joined")},
        ),  # 第三區：時間欄位（唯讀）
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

    # 設定唯讀欄位：避免誤改系統時間欄位
    readonly_fields = ("date_joined", "last_login")

    # ======== 中文欄位標題（列表） ========
    @admin.display(description="電子郵件")
    def col_email(self, obj: User):
        return obj.email

    @admin.display(description="角色")
    def col_role(self, obj: User):
        return obj.role

    @admin.display(boolean=True, description="管理員")
    def col_is_staff(self, obj: User):
        return obj.is_staff

    @admin.display(boolean=True, description="超級管理員")
    def col_is_superuser(self, obj: User):
        return obj.is_superuser

    @admin.display(boolean=True, description="啟用")
    def col_is_active(self, obj: User):
        return obj.is_active

    @admin.display(description="建立時間")
    def col_date_joined(self, obj: User):
        return obj.date_joined

    @admin.display(description="ID")
    def col_id(self, obj: User):
        return obj.id


# 將自訂 User 模型註冊到 Django admin，並用剛剛定義的 UserAdmin 來管理
admin.site.register(User, UserAdmin)
