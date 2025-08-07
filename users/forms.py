# users/forms.py

from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from .models import User


class UserRegisterForm(forms.ModelForm):
    password1 = forms.CharField(label="密碼", widget=forms.PasswordInput)
    password2 = forms.CharField(label="確認密碼", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["email"]

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

        if commit:
            user.save()
        return user
