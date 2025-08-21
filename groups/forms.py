from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Group, GroupMembership
from pi_devices.models import Device


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name"]
        labels = {"name": _("群組名稱")}
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": _("請輸入群組名稱（例如：客廳、家人共享）"),
                    "class": "form-control",
                }
            ),
        }
        error_messages = {
            "name": {
                "required": _("請輸入群組名稱"),
            }
        }


class GroupCreateForm(forms.ModelForm):
    """建立群組時，允許擁有者一次選擇多台自己的裝置一併加入群組。"""

    devices = forms.ModelMultipleChoiceField(
        label=_("要加入的裝置"),
        queryset=Device.objects.none(),  # 進 __init__ 再依使用者帶入
        required=True,
        help_text=_("請至少選擇一台裝置"),
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": "8"}),
    )

    class Meta:
        model = Group
        fields = ["name", "devices"]
        labels = {"name": _("群組名稱")}
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": _("請輸入群組名稱（例如：幼獅的窩）"),
                    "class": "form-control",
                }
            ),
        }
        error_messages = {
            "name": {"required": _("請輸入群組名稱")},
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user  # 存下使用者，clean() 要用

        qs = Device.objects.none()
        if user is not None:
            qs = Device.objects.filter(user=user).order_by(
                "display_name", "serial_number", "id"
            )
        self.fields["devices"].queryset = qs

        # 選項顯示更友善：「顯示名稱（序號）」
        self.fields["devices"].label_from_instance = lambda d: (
            f"{getattr(d, 'display_name', '') or d.serial_number}（{d.serial_number}）"
        )

        # 無裝置時給更清楚的提示（可選：也可不 disable）
        if not qs.exists():
            self.fields["devices"].widget.attrs["disabled"] = True
            self.fields["devices"].help_text = _(
                "你目前沒有可選的裝置，先建立群組，之後再加入也可以。"
            )

    def clean(self):
        """伺服端二次驗證：確保所有選取的裝置都屬於目前登入者。"""
        cleaned = super().clean()
        devices = cleaned.get("devices") or []
        if self.user is not None and devices:
            invalid = [d for d in devices if d.user_id != self.user.id]
            if invalid:
                raise forms.ValidationError(_("你選擇的裝置中包含不屬於你的項目。"))
        return cleaned


class AddMemberForm(forms.Form):
    email = forms.EmailField(
        label=_("成員 Email"),
        widget=forms.EmailInput(
            attrs={"placeholder": _("name@example.com"), "class": "form-control"}
        ),
        error_messages={
            "required": _("請輸入 Email"),
            "invalid": _("Email 格式不正確"),
        },
    )
    role = forms.ChoiceField(
        label=_("角色"),
        choices=[("", _("請選擇角色"))] + list(GroupMembership.ROLE_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
        error_messages={"required": _("請選擇角色")},
    )
    device = forms.ModelChoiceField(
        label=_("裝置"),
        queryset=Device.objects.none(),  # 由 view 依群組動態帶入：group.devices.all()
        empty_label=_("請選擇裝置"),
        widget=forms.Select(attrs={"class": "form-select"}),
        error_messages={"required": _("請選擇裝置")},
    )


class UpdateMemberForm(forms.Form):
    role = forms.ChoiceField(
        label=_("角色"),
        choices=[("", _("請選擇角色"))] + list(GroupMembership.ROLE_CHOICES),
        widget=forms.Select(attrs={"class": "form-select"}),
        error_messages={"required": _("請選擇角色")},
    )
