# users/forms.py

from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from .models import User
from pi_devices.models import Device


class UserRegisterForm(forms.ModelForm):
    password1 = forms.CharField(label="密碼", widget=forms.PasswordInput)
    password2 = forms.CharField(label="確認密碼", widget=forms.PasswordInput)
    device_serial = forms.CharField(label="設備序號")  # 額外欄位：輸入綁定用的設備序號
    verification_code = forms.CharField(label="驗證碼")  # 額外欄位：輸入該設備的驗證碼

    class Meta:
        model = User
        fields = ["email"]  # 表單只顯示 email，其餘欄位為自訂欄位

    def __init__(self, *args, **kwargs):
        # 在建立表單時，可以額外傳入 token ，這個 token 是用來找到對應的設備。
        self.token = kwargs.pop("token", None)
        super().__init__(*args, **kwargs)

    def clean_password2(self):
        pw1 = self.cleaned_data.get("password1")
        pw2 = self.cleaned_data.get("password2")
        if pw1 and pw2 and pw1 != pw2:
            raise forms.ValidationError("請重新輸入，輸入的密碼不一致")
        return pw2

    def save(self, commit=True):
        user = super().save(commit=False)
        # Django 內建的密碼加密方法，Django 會自動對密碼進行「加鹽」處理
        user.set_password(self.cleaned_data["password1"])

        # 保護：註冊者永遠無法進 Django Admin
        user.is_staff = False
        user.is_superuser = False

        # 設定設備與使用者的綁定關係
        user.device = self.device
        user.device.is_bound = True
        user.device.save()

        if commit:
            user.save()
        return user

    def clean(self):
        # 驗證設備序號與驗證碼
        cleaned_data = super().clean()
        serial = cleaned_data.get("device_serial")
        code = cleaned_data.get("verification_code")
        token = self.token

        if serial and code:
            try:
                device = Device.objects.get(token=token)
            except Device.DoesNotExist:
                raise forms.ValidationError("找不到對應的設備 Token")
            if serial and device.serial_number != serial:
                raise forms.ValidationError("設備序號不一致")

            if device.verification_code != code:
                raise forms.ValidationError("驗證碼錯誤")

            if device.is_bound:
                raise forms.ValidationError("此設備已綁定")
            self.device = device  # 驗證通過後，存放設備供 save() 使用
        return cleaned_data


class InviteRegisterForm(forms.ModelForm):
    password1 = forms.CharField(label="密碼", widget=forms.PasswordInput)
    password2 = forms.CharField(label="確認密碼", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["email"]  # 只需要 Email

    def __init__(self, *args, fixed_email: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fixed_email = (fixed_email or "").lower()
        if self.fixed_email:
            self.fields["email"].initial = self.fixed_email

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
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
        user.set_password(self.cleaned_data["password1"])
        # 受邀註冊 → 一般會員；不綁裝置、不改 is_staff/superuser
        user.role = "user"
        if commit:
            user.save()
        return user
