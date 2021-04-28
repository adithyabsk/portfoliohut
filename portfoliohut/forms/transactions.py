from datetime import datetime
from decimal import Decimal

import pandas as pd
import pandas_market_calendars as mcal
from django import forms
from django.core.validators import FileExtensionValidator
from django.db import models, transaction
from django.db.models import F, Sum
from django.forms.widgets import DateInput, TimeInput
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from portfoliohut.models import (
    CashActions,
    FinancialActionType,
    HistoricalEquity,
    Profile,
    Transaction,
)


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


def _is_duplicate(
    profile: Profile,
    date: datetime.date,
    time: datetime.time,
    ticker: str,
):
    tqset = Transaction.objects.filter(
        profile=profile, date=date, time=time, ticker=ticker
    )
    return tqset.exists()


class BaseTransactionForm(forms.ModelForm):
    """Shared cleaning attributes between StockForm and CashForm."""

    action = forms.CharField()  # Note this will be overridden

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
        self.profile = kwargs.pop("profile", None)
        super().__init__(*args, **kwargs)
        today = timezone.now().date()
        self.fields["date"].widget.attrs.update({"max": today})

    def clean(self):
        cleaned_data = super().clean()

        # Validate time: Transaction cannot be in the future
        date = cleaned_data.get("date")
        time = cleaned_data.get("time")
        if datetime.combine(date, time) > timezone.now().replace(tzinfo=None):
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
    """Form that encodes stock purchase data.

    Attributes:
        action: a value from `StockAction`
        date: The date of the stock purchase
        time: The time of the stock purchase
        price: The price of the stock
        ticker: The ticker for the stock
        quantity: The amount of stock

    """

    action = forms.CharField(widget=forms.Select(choices=StockAction.choices))

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

        # Check the model based parameters first and if not short circuit the clean
        # this prevents errors downstream (i.e. missing fields)
        if not self.is_valid():
            return cleaned_data

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
        price = cleaned_data.get("price")
        high = ticker_date_qset.first().high
        low = ticker_date_qset.first().low
        if not low <= price <= high:
            raise forms.ValidationError(
                f"Invalid stock price: Price must be between ${low} and ${high} on "
                f"{date.strftime('%m/%d/%Y')}"
            )

        # Validate BUY: User cannot buy stock worth more than the value of cash in user's account at
        # the time of purchase
        # Pop action as it is not used downstream
        action = cleaned_data.pop("action")
        quantity = cleaned_data.get("quantity")
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

        if _is_duplicate(self.profile, date, time, ticker):
            raise forms.ValidationError("This transaction looks like a duplicate")

        # Set quantity based on buy/sell (negative quantity is sell in Transaction)
        multiplier = 1 if action == StockAction.BUY else -1
        cleaned_data["quantity"] *= multiplier

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

    def save(self, *, skip_portfolio_reset=False):
        Transaction.objects.create_equity_transaction(
            profile=self.profile, type=FinancialActionType.EQUITY, **self.cleaned_data
        )


class CashForm(BaseTransactionForm):
    """Form that encodes stock purchase data.

    Attributes:
        action: a value from `CashAction`
        date: The date of the account action
        time: The time of the account action
        price: The amount to deposit of withdraw

    """

    action = forms.CharField(widget=forms.Select(choices=CashAction.choices))

    class Meta(BaseTransactionForm.Meta):
        labels = {
            **BaseTransactionForm.Meta.labels,
            "price": "Amount",
        }

    field_order = [*BaseTransactionForm.field_order, "price"]

    def clean(self):
        cleaned_data = super().clean()

        # Check the model based parameters first and if not short circuit the clean
        # this prevents errors downstream (i.e. missing fields)
        if not self.is_valid():
            return cleaned_data

        # Validate WITHDRAW: User cannot withdraw more money than is in user's account on the
        # date/time of transaction
        # Pop action as it is not used downstream
        action = cleaned_data.pop("action")
        price = cleaned_data.get("price")
        date = cleaned_data.get("date")
        time = cleaned_data.get("time")
        if action == CashAction.WITHDRAW:
            if not _is_cash_available(self.profile, date, time, price):
                raise forms.ValidationError(
                    "Invalid WITHDRAW: There is not enough cash in your account on the given "
                    "date/time to complete this transaction"
                )

        if _is_duplicate(self.profile, date, time, "-"):
            raise forms.ValidationError("This transaction looks like a duplicate")

        # Set quantity based on buy/sell (negative quantity is withdraw in Transaction)
        cleaned_data["quantity"] = 1 if action == CashAction.DEPOSIT else -1

        return cleaned_data

    def clean_action(self):
        action = self.cleaned_data.get("action")
        if action not in CashAction:
            raise forms.ValidationError(
                "Invalid action: Cash transactions must be DEPOSIT or WITHDRAW"
            )
        return action

    def save(self, *, skip_portfolio_reset=False):
        Transaction.objects.create_cash_transaction(
            profile=self.profile,
            type=FinancialActionType.EXTERNAL_CASH,
            **self.cleaned_data,
        )


class CSVForm(forms.Form):
    csv_file = forms.FileField(
        validators=[FileExtensionValidator(["csv"], "Only csv files are allowed")]
    )

    def __init__(self, *args, **kwargs):
        self.profile = kwargs.pop("profile", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        try:
            csv_df = pd.read_csv(cleaned_data.get("csv_file"))
        except (pd.errors.ParseError, ValueError):
            raise forms.ValidationError("Could not read CSV.")

        if csv_df.columns.tolist() != [
            "action",
            "date",
            "time",
            "price",
            "ticker",
            "quantity",
        ]:
            raise forms.ValidationError("Malformed CSV columns.")

        with transaction.atomic():
            for idx, row in csv_df.iterrows():
                FormClass = StockForm if row["action"] in StockAction else CashForm
                row_form = FormClass(row.to_dict(), profile=self.profile)
                if not row_form.is_valid():
                    for error_message in row_form.errors.values():
                        self.add_error(None, error_message)

                    raise forms.ValidationError(f"Error occurred on row {idx+1}")

                row_form.save(skip_portfolio_reset=True)

            Transaction.objects._reset_portfolio_cache(profile=self.profile)
