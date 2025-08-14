from django.contrib.auth.models import (
    AbstractBaseUser,  # 提供密碼雜湊與驗證的基底類
    BaseUserManager,  # 自訂使用者模型時需要的 Manager
    PermissionsMixin,  # 提供 is_superuser、groups、user_permissions
)
from django.db import models
from django.utils.html import format_html  # 產生安全 HTML（用於 admin 顯示徽章等）
from django.conf import settings
from pi_devices.models import (
    Device,
)  # 你的裝置模型（需具備 is_online(window_seconds) 等）
from django.utils import timezone
from datetime import timedelta


class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        """
        建立一般使用者：
        - email 必填，並會正規化
        - 密碼使用 set_password 雜湊儲存
        - 其他欄位從 extra_fields 帶入
        """
        if not email:
            raise ValueError("Email必要填入")
        email = self.normalize_email(email)  # 正規化 email（小寫網域等）
        user = self.model(email=email, **extra_fields)  # 建立模型實例（尚未存檔）
        user.set_password(password)  # 以 Django 方式雜湊密碼
        user.save()  # 寫入資料庫
        return user

    def create_superuser(self, email, password=None, **extra_fields):

        extra_fields.setdefault("is_staff", True)  # 能登入 Django admin
        extra_fields.setdefault("is_superuser", True)  # 擁有所有權限
        extra_fields.setdefault("role", "superadmin")  # 自訂角色設為最高層級

        # 防呆：避免被外部覆寫成 False
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    自訂使用者模型：
    - 使用 email 當作登入識別（取代 username）
    - 角色欄位 role 作為自訂權限邏輯的輔助
    - 可選擇性綁定一台 Device（用於線上狀態判斷）
    - 支援邀請制度（記錄邀請人）
    """

    # 角色選項：定義系統中的使用者層級
    ROLE_CHOICES = [
        ("user", "User"),  # 一般使用者
        ("admin", "Admin"),  # 管理員
        ("superadmin", "SuperAdmin"),  # 超級管理員
    ]

    # === 基本帳號資訊 ===
    email = models.EmailField(unique=True)  # 當作帳號使用，需唯一（取代 username）
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="user",  # 新註冊使用者預設為一般使用者
        help_text="使用者在系統中的角色層級",
    )

    # === 邀請制度 ===
    invited_by = models.ForeignKey(
        "self",  # 自我關聯：紀錄該使用者由誰邀請
        null=True,
        blank=True,
        on_delete=models.SET_NULL,  # 邀請人刪除時設為 NULL（保護被邀請者）
        related_name="invited_users",  # 反向關聯：某使用者.invited_users -> 被他邀請的人
        help_text="邀請此使用者的人",
    )

    member_groups = models.ManyToManyField(
        "groups.Group",
        through="groups.GroupMembership",
        related_name="users",  # group.users.all() 依然好用
        blank=True,
    )

    # === Django 標準欄位 ===
    is_active = models.BooleanField(default=True)  # 是否啟用帳號（Django 慣例）
    is_staff = models.BooleanField(default=False)  # 是否能登入 Django admin
    date_joined = models.DateTimeField(auto_now_add=True)  # 建立時間（自動設定）

    # # === 裝置綁定 ===
    # device = models.OneToOneField(
    #     Device,
    #     null=True,
    #     blank=True,
    #     on_delete=models.SET_NULL,  # 裝置刪除時，使用者的 device 設為 NULL
    #     help_text="綁定的樹梅派設備，如有（用於判斷線上狀態）",
    # )

    # === Django 設定 ===
    objects = UserManager()  # 指定自訂 Manager，供 createsuperuser 等使用

    USERNAME_FIELD = "email"  # 指定用 email 當作登入識別（取代 username）
    REQUIRED_FIELDS = []  # createsuperuser 額外必填欄位（空表示不用）

    # === 線上狀態判斷 ===
    def is_online(self, window_seconds: int | None = None) -> bool:
        window = window_seconds or getattr(settings, "DEVICE_ONLINE_WINDOW_SECONDS", 60)
        # 只要有任一台裝置在線，就視為在線
        return self.devices.filter(
            last_ping__gte=timezone.now() - timedelta(seconds=window)
        ).exists()

    @property
    def online(self) -> str:
        """
        中文狀態字串（方便模板直接顯示）：
        - 回傳 "在線" 或 "離線"
        - 使用 @property 讓模板可用 {{ user.online }} 而非 {{ user.online() }}
        """
        return "在線" if self.is_online() else "離線"

    def online_badge(self) -> str:
        """
        以彩色徽章顯示線上狀態（可於 admin list_display 使用）：
        - 綠色：在線
        - 灰色：離線
        - 使用 format_html 確保 HTML 安全性
        """
        status = "在線" if self.is_online() else "離線"
        color = "green" if status == "在線" else "gray"
        return format_html(
            '<span style="color: white; background-color: {}; padding: 3px 6px; border-radius: 4px; font-size: 12px;">{}</span>',
            color,
            status,
        )

    # 設定在 Django admin 列表頁面的欄位標題
    online_badge.short_description = "線上狀態"

    # === 基本方法 ===
    def __str__(self):
        # 在 Django admin、shell、或 print() 時顯示 > 回傳使用者的 email
        return self.email

    # === 權限輔助方法 ===
    def is_admin(self):
        return self.role == "admin"

    def is_superadmin(self):
        # 檢查是否為超級管理員：
        return self.role == "superadmin"

    class Meta:
        verbose_name = "使用者"
        verbose_name_plural = "使用者"
        db_table = "users_user"  # 可選：自訂資料表名稱
        ordering = ["-date_joined"]  # 預設排序：最新註冊的在前
