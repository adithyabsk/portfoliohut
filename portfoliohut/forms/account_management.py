import re

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils.html import strip_tags


def sanitize(input_str):
    return strip_tags(input_str)


class LoginForm(forms.Form):
    """Validate login registration details."""

    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput())

    def clean(self):
        cleaned_data = super().clean()

        username = cleaned_data.get("username")
        password = cleaned_data.get("password")
        user = authenticate(username=username, password=password)
        if user is None:
            raise forms.ValidationError("Invalid username password combination.")

        return cleaned_data

    def clean_username(self):
        username = self.cleaned_data.get("username")
        username = sanitize(username)
        if re.search(r"([a-zA-Z\d])+$", username) is None:
            raise forms.ValidationError("Invalid username, no characters allowed.")

        return username

    def clean_password(self):
        password = self.cleaned_data.get("password")
        password = sanitize(password)
        return password


class RegisterForm(forms.Form):
    """Validate registration details."""

    first_name = forms.CharField()
    last_name = forms.CharField()
    email = forms.EmailField()
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput())
    confirm_password = forms.CharField(widget=forms.PasswordInput())

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("The passwords do not match")

        return cleaned_data

    def clean_first_name(self):
        first_name = self.cleaned_data.get("first_name")
        first_name = sanitize(first_name)
        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get("last_name")
        last_name = sanitize(last_name)
        return last_name

    def clean_email(self):
        email = self.cleaned_data.get("email")
        email = sanitize(email)
        return email

    def clean_username(self):
        username = self.cleaned_data.get("username")

        # Sanitize the input
        username = sanitize(username)

        # Check if username is taken
        if User.objects.filter(username__exact=username):
            raise forms.ValidationError("Username is taken.")

        return username

    def clean_password(self):
        password = self.cleaned_data.get("password")
        password = sanitize(password)
        return password

    def clean_confirm_password(self):
        confirm_password = self.cleaned_data.get("confirm_password")
        confirm_password = sanitize(confirm_password)
        return confirm_password
