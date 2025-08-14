from django import forms
from .models import Device


class DeviceNameForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = ["display_name"]
        labels = {"display_name": "裝置名稱"}


class BindDeviceForm(forms.Form):
    serial_number = forms.CharField(label="設備序號", max_length=100)
    verification_code = forms.CharField(label="驗證碼", max_length=20)

    def clean(self):
        cleaned = super().clean()
        sn = cleaned.get("serial_number")
        code = cleaned.get("verification_code")

        if not sn or not code:
            return cleaned

        try:
            device = Device.objects.get(serial_number=sn)
        except Device.DoesNotExist:
            raise forms.ValidationError("找不到此設備序號。")

        if device.verification_code != code:
            raise forms.ValidationError("驗證碼不正確。")

        if device.is_bound or device.user_id is not None:
            raise forms.ValidationError("此設備已被其他帳號綁定。")

        cleaned["device"] = device
        return cleaned
