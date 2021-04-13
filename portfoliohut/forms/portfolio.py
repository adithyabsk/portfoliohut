"""Social Network Forms."""
from django import forms

from portfoliohut.models import Profile


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = {
            "bio",
        }
        widgets = {
            "bio": forms.Textarea(),
        }
