from django import forms
from .models import Group, GroupMembership


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name"]


class AddMemberForm(forms.Form):
    email = forms.EmailField(label="成員 Email")
    role = forms.ChoiceField(
        choices=GroupMembership.ROLE_CHOICES, initial="operator", label="角色"
    )


class UpdateMemberForm(forms.Form):
    role = forms.ChoiceField(choices=GroupMembership.ROLE_CHOICES, label="角色")
