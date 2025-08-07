from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models


# 自訂 User Manager，負責建立使用者和超級使用者的邏輯
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        # 建立一般使用者帳號，必填 email
        if not email:
            raise ValueError("Email必要填入")  # 沒有 email 則拋錯
        email = self.normalize_email(email)  # 將 email 正規化(如全部小寫)
        user = self.model(
            email=email, **extra_fields
        )  # 建立 User 物件，但還沒存入資料庫
        user.set_password(password)  # 設定密碼（加密）
        user.save()  # 寫入資料庫
        return user  # 回傳 User 物件

    def create_superuser(self, email, password=None, **extra_fields):
        # 建立超級使用者(管理員)帳號，並設定必要權限 setdefault 會先檢查字典裡是否有這個鍵，如果已經存在，就保持不變；如果不存在，才給它一個預設值。
        extra_fields.setdefault("is_staff", True)  # 管理員權限標記
        extra_fields.setdefault("is_superuser", True)  # 超級使用者權限標記
        extra_fields.setdefault("role", "superadmin")  # 自訂角色欄位設為 superadmin
        return self.create_user(
            email, password, **extra_fields
        )  # 呼叫 create_user 來完成建立


# 自訂使用者模型，繼承 Django 認證基本功能與權限功能
class User(AbstractBaseUser, PermissionsMixin):
    # 使用者角色選項，定義該欄位可用的字串與顯示名稱
    ROLE_CHOICES = [
        ("user", "User"),
        ("admin", "Admin"),
        ("superadmin", "SuperAdmin"),
    ]

    email = models.EmailField(unique=True)  # 電子郵件欄位且唯一，作為登入帳號
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default="user"
    )  # 角色欄位預設為 user
    # invited_by 自我關聯欄位，紀錄是被哪個 User 邀請註冊，可為空
    invited_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invited_users",  # 反向關聯名稱，查邀請此人的清單用
    )
    is_active = models.BooleanField(default=True)  # 帳號是否啟用，False 將無法登入
    is_staff = models.BooleanField(
        default=False
    )  # 是否有管理站台的權限（進入 admin 後台）
    date_joined = models.DateTimeField(auto_now_add=True)  # 建立帳號的時間，自動填入

    objects = UserManager()  # 指定自訂的 User Manager 負責建立使用者和超級使用者

    USERNAME_FIELD = "email"  # 指定用來登入的欄位為 email
    REQUIRED_FIELDS = (
        []
    )  # 建議在此加上 'role' 欄位，若要強制 superuser 建立時輸入此欄位

    def __str__(self):
        # 當用 print(user) 或 admin 顯示使用者名稱時，回傳 email 字串呈現
        return self.email

    def is_admin(self):
        # 方便判斷此使用者是否是 admin 角色，回傳 True / False
        return self.role == "admin"

    def is_superadmin(self):
        # 方便判斷此使用者是否是 superadmin 角色，回傳 True / False
        return self.role == "superadmin"
