from datetime import datetime
from decimal import Decimal

import pandas_market_calendars as mcal
from django import forms
from django.db import models
from django.db.models import F, Sum
from django.forms.widgets import DateInput, TimeInput
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from portfoliohut.models import CashActions, HistoricalEquity, Profile, Transaction


class StockAction(models.TextChoices):
    BUY = "buy", _("Buy")
    SELL = "sell", _("Sell")


class CashAction(models.TextChoices):
    DEPOSIT = "deposit", _("Deposit")
    WITHDRAW = "withdraw", _("Withdraw")


def _is_cash_available(
    profile: Profile, date: datetime.date, time: datetime.time, value: Decimal
) -> bool:
    """Validate if a `Profile` contains enough balance to fund a transaction.

    Args:
        profile: The `User.profile` instance
        date: The date of the transaction
        time: The time of the transaction
        value: The cost of the transaction

    """
    cash_transactions = Transaction.objects.filter(
        profile=profile,
        type__in=CashActions,
        date__lte=date,
    ).exclude(date=date, time__gt=time)

    if not cash_transactions.exists():
        return False

    cash_at_time = cash_transactions.aggregate(
        available_cash=Sum(
            F("price") * F("quantity"), output_field=models.DecimalField()
        )
    )["available_cash"]

    return cash_at_time >= value


def _is_shares_available(
    profile: Profile,
    date: datetime.date,
    time: datetime.time,
    ticker: str,
    quantity: int,
) -> bool:
    """Validate if there are enough shares for a sell action.

    Args:
        profile: The `User.profile` instance
        date: The date of the transaction
        time: The time of the transaction
        ticker: The stock's ticker
        quantity: The number of shares to be sold

    """
    stock_transactions = Transaction.objects.filter(
        profile=profile, ticker=ticker, date__lte=date
    ).exclude(date=date, time__gt=time)

    if not stock_transactions.exists():
        return False

    num_shares = stock_transactions.aggregate(sum=Sum("quantity"))["sum"]

    return num_shares >= quantity


class CSVForm(forms.Form):
    file = forms.FileField(allow_empty_file=True)


class BaseTransactionForm(forms.ModelForm):
    """Shared cleaning attributes between StockForm and CashForm."""

    class Meta:
        model = Transaction
        fields = {"action", "date", "time", "price"}
        labels = {
            "action": "Transaction Type",
            "date": "Date",
            "time": "Time (ET)",
        }
        widgets = {
            "date": DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "time": TimeInput(attrs={"type": "time"}),
        }

    field_order = ["action", "date", "time"]

    def __init__(self, *args, **kwargs):
        self.profile = kwargs.pop("profile")
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        # Validate time: Transaction cannot be in the future
        date = cleaned_data.get("date")
        time = cleaned_data.get("time")
        if datetime.combine(date, time) > timezone.now():
            raise forms.ValidationError("Invalid time: Time cannot be in the future")

        return cleaned_data

    def clean_action(self):
        raise NotImplementedError

    def clean_date(self):
        date = self.cleaned_data.get("date")
        if date > timezone.now().date():
            raise forms.ValidationError("Invalid date: Date cannot be in the future")
        return date

    def clean_price(self):
        price = self.cleaned_data.get("price")
        if price <= 0:
            raise forms.ValidationError(
                "Invalid price: Value must be strictly positive"
            )
        return price


class StockForm(BaseTransactionForm):
    action = forms.CharField(widget=forms.Select(choices=CashAction))

    class Meta(BaseTransactionForm.Meta):
        fields = {*BaseTransactionForm.Meta.fields, "ticker", "quantity"}
        labels = {
            **BaseTransactionForm.Meta.labels,
            "ticker": "Ticker",
            "price": "Price at Time of Transaction",
            "quantity": "Number of Shares",
        }

    field_order = [*BaseTransactionForm.field_order, "ticker", "quantity", "price"]

    def clean(self):
        cleaned_data = super().clean()

        # Validate ticker: Ticker must exist in the NYSE
        ticker = cleaned_data.get("ticker")
        ticker_qset = HistoricalEquity.objects.get_ticker(ticker)
        if not ticker_qset.exists():
            raise forms.ValidationError("Invalid ticker: Ticker must be in the NYSE")

        # Validate date: NYSE must be open on the given day and the date cannot be in the future
        date = cleaned_data.get("date")
        ticker_date_qset = ticker_qset.filter(date=date)
        if not ticker_date_qset.exists():
            raise forms.ValidationError(
                "Invalid date: NYSE was not open on the given date, or the date is in the future"
            )

        # Validate time: NYSE must be open at the given time of transaction
        time = cleaned_data.get("time")
        nyse = mcal.get_calendar("NYSE")
        day = nyse.schedule(start_date=date, end_date=date)
        for m in ["market_open", "market_close"]:
            # Convert times to ET https://github.com/rsheftel/pandas_market_calendars/issues/42
            day[m] = day[m].dt.tz_convert("America/New_York")
        market_open = day.iloc[0]["market_open"].time()
        market_close = day.iloc[0]["market_close"].time()
        if not market_open <= time <= market_close:
            raise forms.ValidationError(
                f"Invalid time: Time of purchase must be between {market_open.strftime('%I:%M %p')}"
                f" and {market_close.strftime('%I:%M %p')} on {date.strftime('%m/%d/%Y')}"
            )

        # Validate price: Price must be between the lowest and highest prices for the ticker on the
        # given daTe
        price = self.cleaned_data.get("price")
        high = ticker_date_qset.first().high
        low = ticker_date_qset.first().low
        if not low <= price <= high:
            raise forms.ValidationError(
                f"Invalid stock price: Price must be between ${low} and ${high} on "
                f"{date.strftime('%m/%d/%Y')}"
            )

        # Validate BUY: User cannot buy stock worth more than the value of cash in user's account at
        # the time of purchase
        action = self.cleaned_data.get("action")
        quantity = self.cleaned_data.get("quantity")
        if action == "buy":
            if not _is_cash_available(self.profile, date, time, price * quantity):
                raise forms.ValidationError(
                    "Invalid BUY: There is not enough cash in your account on the given date/time "
                    "to complete this transaction"
                )

        # Validate SELL: User can't sell more shares than user owned on the date/time of sale
        else:
            if not _is_shares_available(self.profile, date, time, ticker, quantity):
                raise forms.ValidationError(
                    f"Invalid SELL: There are not enough shares of {ticker} in your account on the "
                    "given date/time to complete this transaction"
                )

        return cleaned_data

    def clean_action(self):
        action = self.cleaned_data.get("action")
        if action not in StockAction:
            raise forms.ValidationError(
                "Invalid action: Stock transactions must be BUY or SELL"
            )
        return action

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")
        if quantity <= 0:
            raise forms.ValidationError(
                "Invalid number of shares: Quantity must be strictly positive"
            )
        return quantity


class CashForm(BaseTransactionForm):
    action = forms.CharField(widget=forms.Select(choices=CashAction))

    class Meta(BaseTransactionForm.Meta):
        labels = {
            **BaseTransactionForm.Meta.labels,
            "price": "Amount",
        }

    field_order = [*BaseTransactionForm.field_order, "price"]

    def clean(self):
        cleaned_data = super().clean()

        # Validate WITHDRAW: User cannot withdraw more money than is in user's account on the
        # date/time of transaction
        action = cleaned_data.get("action")
        price = cleaned_data.get("price")
        date = cleaned_data.get("date")
        time = cleaned_data.get("time")
        if action == "withdraw":
            valid_withdraw = _is_cash_available(self.profile, date, time, price, 1)
            if not valid_withdraw:
                raise forms.ValidationError(
                    "Invalid WITHDRAW: There is not enough cash in your account on the given "
                    "date/time to complete this transaction"
                )

        return cleaned_data

    def clean_action(self):
        action = self.cleaned_data.get("action")
        if action not in CashAction:
            raise forms.ValidationError(
                "Invalid action: Cash transactions must be DEPOSIT or WITHDRAW"
            )
        return action
