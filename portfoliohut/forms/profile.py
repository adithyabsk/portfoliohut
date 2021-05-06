from django import forms
from django.utils.html import strip_tags

from portfoliohut.models import Profile


def sanitize(input_str):
    # input_str = input_str.replace("<", "&lt;")
    # input_str = input_str.replace(">", "&gt;")
    return strip_tags(input_str)


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = {
            "bio",
            "profile_type",
        }
        widgets = {
            "bio": forms.Textarea(
                attrs={
                    "rows": 3,
                    "cols": 100,
                    "style": "line-height: 1.5; border-radius: 5px;border: 1px solid #ccc;box-shadow: 1px 1px 1px #999; height: 15%;",
                }
            ),
            "profile_type": forms.Select(
                attrs={
                    "class": "narrow-select",
                }
            ),
        }
        labels = {"bio": "", "profile_type": "Profile Visibility"}

    field_order = ["bio", "profile_type"]

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def clean_bio(self):
        bio = self.cleaned_data.get("bio")
        bio = sanitize(bio)
        return bio

    def clean_profile_type(self):
        profile_type = self.cleaned_data.get("profile_type")
        if profile_type not in ["public", "private"]:
            raise forms.ValidationError(
                "Invalid profile type: Profile must be PUBLIC or PRIVATE"
            )

        return profile_type
