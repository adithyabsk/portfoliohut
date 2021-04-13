from django import forms
from django.utils import timezone

from portfoliohut.models import CashBalance, Stock


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
