from django import forms
from .models import Group, GroupMembership
from pi_devices.models import Device


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name"]


class AddMemberForm(forms.Form):
    email = forms.EmailField(label="成員 Email")
    role = forms.ChoiceField(
        choices=GroupMembership.ROLE_CHOICES, initial="operator", label="角色"
    )
    device = forms.ModelChoiceField(label="裝置", queryset=Device.objects.none())


class UpdateMemberForm(forms.Form):
    role = forms.ChoiceField(choices=GroupMembership.ROLE_CHOICES, label="角色")
