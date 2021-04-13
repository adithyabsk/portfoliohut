from datetime import date, timedelta

import yfinance as yf
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
            "action": "Transaction Type",
            "ticker": "Ticker",
            "date_time": "Date and Time of Transaction",
            "price": "Price at Time of Transaction",
            "quantity": "Number of Shares",
        }

    field_order = ["action", "ticker", "date_time", "price", "quantity"]

    def clean(self):
        cleaned_data = super().clean()
        ticker = self.cleaned_data.get("ticker")
        date_time = self.cleaned_data.get("date_time")
        price = self.cleaned_data.get("price")

        # Get ticker price on given date
        yf_ticker = yf.Ticker(ticker)
        df = None
        if date_time.date() == date.today():
            df = yf_ticker.history(period="1d")
        else:
            df = yf_ticker.history(
                start=date_time.date(),
                end=(date_time.date() + timedelta(1)),
                interval="1d",
            )

        # Compare it to the given price
        if df.empty:
            raise forms.ValidationError(
                "Invalid date/time: NYSE was closed on the given date"
            )
        if (price < df["Low"].iloc[0]) or (df["High"].iloc[0] < price):
            error_str = "Invalid stock price: price should be between $"
            error_str += str(df["Low"].iloc[0]) + " and $" + str(df["High"].iloc[0])
            error_str += " on " + str(date_time.date())
            raise forms.ValidationError(error_str)

        return cleaned_data

    def clean_ticker(self):
        ticker = self.cleaned_data.get("ticker")
        yf_ticker = yf.Ticker(ticker)
        df = yf_ticker.history(period="1d")
        if df.empty:
            raise forms.ValidationError("Invalid ticker: must be a ticker in the NYSE")
        return ticker

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")
        if quantity < 0:
            raise forms.ValidationError("Invalid stock quantity: must be positive")
        return quantity

    def clean_action(self):
        action = self.cleaned_data.get("action")
        if (not action == "buy") and (not action == "sell"):
            raise forms.ValidationError("Invalid action: must be 'BUY' or 'SELL'")
        return action

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price < 0:
            return forms.ValidationError("Invalid stock price: must be positive")
        return price

    def clean_date_time(self):
        date_time = self.cleaned_data.get("date_time")
        if date_time > timezone.now():
            raise forms.ValidationError("Invalid date/time: cannot be in the future")
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
            "action": "Transaction Type",
            "date_time": "Date and Time of Transaction",
            "value": "Dollar Amount",
        }

    field_order = ["action", "date_time", "value"]

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def clean_value(self):
        value = self.cleaned_data.get("value")
        if value < 0:
            raise forms.ValidationError("Invalid cash value: must be positive")
        return value

    def clean_date_time(self):
        date_time = self.cleaned_data.get("date_time")
        if date_time > timezone.now():
            raise forms.ValidationError("Invalid date: cannot be in the future")
        return date_time
