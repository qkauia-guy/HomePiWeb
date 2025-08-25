from django import forms
from .models import Device, DeviceCapability


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


class DeviceCapabilityForm(forms.ModelForm):
    # Django 4.0+ 內建 forms.JSONField 會幫你驗證 JSON
    config = forms.JSONField(
        required=False, initial=dict, help_text='例如：{"pin": 17, "active_high": true}'
    )

    class Meta:
        model = DeviceCapability
        fields = ("name", "kind", "slug", "config", "order", "enabled")


class MemberDeviceACLForm(forms.Form):
    devices = forms.ModelMultipleChoiceField(
        label="可控制的裝置",
        queryset=Device.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, group=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["devices"].queryset = group.devices.order_by("display_name", "id")
