import pandas as pd
import pandas_market_calendars as mcal
from bootstrap_datepicker_plus import DateTimePickerInput
from django import forms
from django.core.validators import FileExtensionValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from portfoliohut.models import (
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


class BaseTransactionForm(forms.ModelForm):
    """Shared cleaning attributes between StockForm and CashForm."""

    action = forms.CharField()  # Note this will be overridden

    class Meta:
        model = Transaction
        fields = {"action", "date_time", "price"}
        labels = {
            "action": "Transaction Type",
            "date_time": "Date/Time (ET)",
        }

    field_order = ["action", "date_time"]

    def __init__(self, *args, **kwargs):
        self.profile: Profile = kwargs.pop("profile", None)
        super().__init__(*args, **kwargs)
        self.fields["date_time"].widget = DateTimePickerInput(
            options={"maxDate": timezone.now().strftime("%Y-%m-%d 23:59:59")},
        )

    def clean_action(self):
        raise NotImplementedError

    def clean_date_time(self):
        date_time = self.cleaned_data.get("date_time")
        date = date_time.date()
        if date_time > timezone.now():
            raise forms.ValidationError("Invalid date: Date cannot be in the future")

        # Validate time: NYSE must be open at the given time of transaction
        nyse = mcal.get_calendar("NYSE")
        # The times are in UTC by default but incoming times are in ET
        day_df = nyse.schedule(start_date=date, end_date=date)
        if date not in day_df.index.date:
            raise forms.ValidationError(
                "Invalid date: Market must be open for all financial transactions."
            )

        return date_time

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
        date_time: The date and time of the stock purchase
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

        # Validate that the ticker exists in our historical cache
        date_time = cleaned_data.get("date_time")
        date = date_time.date()
        ticker_date_qset = ticker_qset.filter(date=date_time.date())
        if not ticker_date_qset.exists():
            raise forms.ValidationError(
                "Invalid date: Could not find the ticker on the given date"
            )

        # Validate time: NYSE must be open at the given time of transaction
        nyse = mcal.get_calendar("NYSE")
        # the times are in UTC by default but incoming times are in ET
        day_df = nyse.schedule(start_date=date, end_date=date)
        cols = ["market_open", "market_close"]

        for m in cols:
            # Convert times to EST https://github.com/rsheftel/pandas_market_calendars/issues/42
            day_df[m] = day_df[m].dt.tz_convert("America/New_York")

        market_open, market_close = day_df.loc[day_df.index[0], cols]
        if not market_open <= date_time <= market_close:
            raise forms.ValidationError(
                f"Invalid time: Time of purchase must be between {market_open:%I:%M %p)}"
                f" and {market_close:%I:%M %p} on {date:%m/%d/%Y}"
            )

        # Validate price: Price must be between the lowest and highest prices for the ticker on the
        # given date
        price = cleaned_data.get("price")
        high = ticker_date_qset.first().high
        low = ticker_date_qset.first().low
        if not low <= price <= high:
            raise forms.ValidationError(
                f"Invalid stock price: Price must be between ${low} and ${high} on "
                f"{date: %m/%d/%Y)}"
            )

        # Validate BUY: User cannot buy stock worth more than the value of cash in user's account at
        # the time of purchase
        # Pop action as it is not used downstream
        action = cleaned_data.pop("action")
        quantity = cleaned_data.get("quantity")
        if action == "buy":
            if not self.profile.is_cash_available(date_time, price * quantity):
                raise forms.ValidationError(
                    "Invalid BUY: There is not enough cash in your account on the given date/time "
                    "to complete this transaction"
                )

        # Validate SELL: User can't sell more shares than user owned on the date/time of sale
        else:
            if not self.profile.is_shares_available(date_time, ticker, quantity):
                raise forms.ValidationError(
                    f"Invalid SELL: There are not enough shares of {ticker} in your account on the "
                    "given date/time to complete this transaction"
                )

        if self.profile.is_duplicate_transaction(date_time, ticker):
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

    def clean_ticker(self):
        ticker = self.cleaned_data.get("ticker")
        ticker = ticker.upper()
        return ticker

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")
        if quantity <= 0:
            raise forms.ValidationError(
                "Invalid number of shares: Quantity must be strictly positive"
            )
        return quantity

    def save(self, *, skip_post_add_steps=False):
        Transaction.objects.create_equity_transaction(
            only_create=skip_post_add_steps,
            profile=self.profile,
            type=FinancialActionType.EQUITY,
            **self.cleaned_data,
        )


class CashForm(BaseTransactionForm):
    """Form that encodes stock purchase data.

    Attributes:
        action: a value from `CashAction`
        date_time: The date/time of the account action
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
        date_time = cleaned_data.get("date_time")
        if action == CashAction.WITHDRAW:
            if not self.profile.is_cash_available(date_time, price):
                raise forms.ValidationError(
                    "Invalid WITHDRAW: There is not enough cash in your account on the given "
                    "date/time to complete this transaction"
                )

        if self.profile.is_duplicate_transaction(date_time, "-"):
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

    def save(self, *, skip_post_add_steps=False):
        Transaction.objects.create_cash_transaction(
            only_create=skip_post_add_steps,
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
            "date_time",
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

                row_form.save(skip_post_add_steps=True)

            Transaction.objects.post_add_transaction_steps(profile=self.profile)
