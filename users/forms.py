# users/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import User
from pi_devices.models import Device


class UserRegisterForm(forms.ModelForm):
    password1 = forms.CharField(label="密碼", widget=forms.PasswordInput)
    password2 = forms.CharField(label="確認密碼", widget=forms.PasswordInput)
    device_serial = forms.CharField(label="設備序號")
    verification_code = forms.CharField(label="驗證碼")

    class Meta:
        model = User
        fields = ["email"]

    def __init__(self, *args, **kwargs):
        # 額外傳入的 device token
        self.token = kwargs.pop("token", None)
        super().__init__(*args, **kwargs)

    def clean_email(self):
        # 建議統一小寫 + 唯一性檢查（若你的 User.email 已是 unique 可保險再檢一次）
        email = (self.cleaned_data.get("email") or "").lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("此 Email 已被註冊，請改用登入")
        return email

    def clean_password2(self):
        pw1 = self.cleaned_data.get("password1")
        pw2 = self.cleaned_data.get("password2")
        if pw1 and pw2 and pw1 != pw2:
            raise ValidationError("請重新輸入，輸入的密碼不一致")
        return pw2

    def clean(self):
        cleaned = super().clean()
        serial = cleaned.get("device_serial")
        code = cleaned.get("verification_code")
        token = self.token

        if serial and code:
            try:
                device = Device.objects.get(token=token)
            except Device.DoesNotExist:
                raise ValidationError("找不到對應的設備 Token")

            if device.serial_number != serial:
                raise ValidationError("設備序號不一致")

            if device.verification_code != code:
                raise ValidationError("驗證碼錯誤")

            if device.is_bound:
                raise ValidationError("此設備已綁定")

            # 驗證通過，留給 save() 使用
            self.device = device
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        if not hasattr(self, "device"):
            # 理論上 clean() 驗證通過才會到 save()
            raise ValidationError("未通過設備驗證，無法完成註冊")

        user = super().save(commit=False)
        user.email = user.email.lower()
        user.set_password(self.cleaned_data["password1"])

        # 註冊者不應成為 staff/superuser
        user.is_staff = False
        user.is_superuser = False

        # 綁定設備
        user.device = self.device
        self.device.is_bound = True

        if commit:
            user.save()
            self.device.save()
        else:
            # 若先不 commit，至少回傳時 device 的 is_bound 也被更新在記憶體中
            pass
        return user


class InviteRegisterForm(forms.ModelForm):
    password1 = forms.CharField(label="密碼", widget=forms.PasswordInput)
    password2 = forms.CharField(label="確認密碼", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["email"]

    def __init__(self, *args, fixed_email: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fixed_email = (fixed_email or "").lower()
        if self.fixed_email:
            self.fields["email"].initial = self.fixed_email

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").lower()
        if self.fixed_email and email != self.fixed_email:
            raise ValidationError("此邀請僅限指定 Email 使用")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("此 Email 已被註冊，請改用登入")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") != cleaned.get("password2"):
            raise ValidationError("兩次密碼不一致")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = user.email.lower()
        user.set_password(self.cleaned_data["password1"])
        user.role = "user"  # 受邀註冊 → 一般會員
        if commit:
            user.save()
        return user
