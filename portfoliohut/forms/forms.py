"""Social Network Forms."""
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils import timezone

from portfoliohut.models.models import CashBalance, Profile, Stock


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

    def clean_username(self):
        # Check if username is taken
        username = self.cleaned_data.get("username")
        if User.objects.filter(username__exact=username):
            raise forms.ValidationError("Username is taken.")

        return username


class CSVForm(forms.Form):
    file = forms.FileField(allow_empty_file=True)


class StockForm(forms.ModelForm):
    class Meta:
        model = Stock
        fields = {"action", "ticker", "date_time", "price", "quantity"}
        labels = {
            "action": "Trasnaction Type",
            "ticker": "Ticker",
            "date_time": "Date and Time of Transaction",
            "price": "Price at Time of Transaction",
            "quantity": "Number of Shares",
        }

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")
        if quantity < 0:
            raise forms.ValidationError("Invalid stock quantity")

        return quantity

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price < 0:
            raise forms.ValidationError("Invalid stock price")

        return price

    def clean_date_time(self):
        date_time = self.cleaned_data.get("date_time")
        if date_time > timezone.now():
            raise forms.ValidationError("Invalid date")
        return date_time


class CashForm(forms.ModelForm):
    class Meta:
        model = CashBalance
        fields = {
            "action",
            "date_time",
            "value",
        }
        labels = {
            "action": "Trasnaction Type",
            "date_time": "Date and Time of Transaction",
            "value": "Dollar Amount",
        }

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def clean_value(self):
        value = self.cleaned_data.get("value")
        if value < 0:
            raise forms.ValidationError("Invalid stock value")

        return value

    def clean_date_time(self):
        date_time = self.cleaned_data.get("date_time")
        if date_time > timezone.now():
            raise forms.ValidationError("Invalid date")
        return date_time


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = {
            "bio",
        }
        widgets = {
            "bio": forms.Textarea(),
        }
