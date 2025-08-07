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

        if serial and code:
            try:
                device = Device.objects.get(serial_number=serial)
            except Device.DoesNotExist:
                raise forms.ValidationError("找不到此設備")
            if device.verification_code != code:
                raise forms.ValidationError("驗證碼錯誤")
            if device.is_bound:
                raise forms.ValidationError("此設備已被綁定")
            self.device = device  # 驗證通過後，存放設備供 save() 使用
        return cleaned_data
