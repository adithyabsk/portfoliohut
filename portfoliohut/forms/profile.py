from django import forms

from portfoliohut.models import Profile


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = {
            "bio",
            "profile_type",
        }
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 2}),
        }

    field_order = ["bio", "profile_type"]

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def clean_profile_type(self):
        profile_type = self.cleaned_data.get("profile_type")
        if (not profile_type == "public") and (not profile_type == "private"):
            raise forms.ValidationError(
                "Invalid profile type: must be 'PUBLIC' or 'PRIVATE'"
            )

        return profile_type
