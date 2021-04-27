import pandas_market_calendars as mcal
from django import forms
from django.db.models import DecimalField, F, Sum
from django.forms.widgets import DateInput, TimeInput
from django.utils import timezone

from portfoliohut.models import FinancialItem, HistoricalEquity, Transaction

STOCK_ACTIONS = [
    ("buy", "BUY"),
    ("sell", "SELL"),
]

CASH_ACTIONS = [
    ("deposit", "DEPOSIT"),
    ("withdraw", "WITHDRAW"),
]


def _validate_cash_is_available(date, time, price, quantity, profile):
    cash_transactions = Transaction.objects.filter(
        profile=profile,
        type__in=[
            FinancialItem.FinancialActionType.EXTERNAL_CASH,
            FinancialItem.FinancialActionType.INTERNAL_CASH,
        ],
        date__lte=date,
    ).exclude(date=date, time__gt=time)

    if not cash_transactions.exists():
        return False

    cash = cash_transactions.aggregate(
        available_cash=Sum(F("price") * F("quantity"), output_field=DecimalField())
    )

    if cash["available_cash"] < price * quantity:
        return False

    return True


def _validate_shares_are_available(date, time, ticker, quantity, profile):
    stock_transactions = Transaction.objects.filter(
        profile=profile, ticker=ticker, date__lte=date
    ).exclude(date=date, time__gt=time)

    if not stock_transactions.exists():
        return False

    num_shares = stock_transactions.aggregate(Sum("quantity"))

    if num_shares["quantity__sum"] < quantity:
        return False

    return True


def _validate_nyse_is_open(date, time):
    nyse = mcal.get_calendar("NYSE")
    day = nyse.schedule(start_date=date, end_date=date)

    for m in ["market_open", "market_close"]:
        # Convert times to EST https://github.com/rsheftel/pandas_market_calendars/issues/42
        day[m] = day[m].dt.tz_convert("America/New_York")

    market_open = day.iloc[0]["market_open"].time()
    market_close = day.iloc[0]["market_close"].time()
    if not (market_open <= time <= market_close):
        return False, market_open, market_close
    return True, market_open, market_close


def _validate_time_not_in_future(date, time):
    if date == timezone.now().date():
        if timezone.localtime().time() < time:
            return False
    return True


def _validate_date_not_in_future(date):
    if timezone.now().date() < date:
        return False
    return True


def _validate_price_is_positive(price):
    if price <= 0:
        return False
    return True


def _validate_action(action, valid_options):
    if action not in valid_options:
        return False
    return True


class CSVForm(forms.Form):
    file = forms.FileField(allow_empty_file=True)


class StockForm(forms.ModelForm):
    action = forms.CharField(widget=forms.Select(choices=STOCK_ACTIONS))

    class Meta:
        model = Transaction
        fields = {"action", "date", "time", "ticker", "quantity", "price"}
        labels = {
            "action": "Transaction Type",
            "ticker": "Ticker",
            "date": "Date",
            "time": "Time (ET)",
            "price": "Price at Time of Transaction",
            "quantity": "Number of Shares",
        }
        widgets = {
            "date": DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "time": TimeInput(attrs={"type": "time"}),
        }

    field_order = ["action", "date", "time", "ticker", "quantity", "price"]

    def __init__(self, *args, **kwargs):
        self.profile = kwargs.pop("profile")
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        # Validate time: Transaction cannot be in the future
        date = self.cleaned_data.get("date")
        time = self.cleaned_data.get("time")
        valid_time = _validate_time_not_in_future(date, time)
        if not valid_time:
            raise forms.ValidationError(
                "Invalid time: Time cannot be in the future if the transaction date is today"
            )

        # Validate ticker: Ticker must exist in the NYSE
        ticker = self.cleaned_data.get("ticker")
        ticker_qset = HistoricalEquity.objects.get_ticker(ticker)
        if not ticker_qset.exists():
            raise forms.ValidationError("Invalid ticker: Ticker must be in the NYSE")

        # Validate date: NYSE must be open on the given day and the date cannot be in the future
        ticker_date_qset = ticker_qset.filter(date=date)
        if not ticker_date_qset.exists():
            raise forms.ValidationError(
                "Invalid date: NYSE was not open on the given date, or the date is in the future"
            )

        # Validate time: NYSE must be open at the given time of transaction
        nyse_open, market_open, market_close = _validate_nyse_is_open(date, time)
        if not nyse_open:
            raise forms.ValidationError(
                "Invalid time: Time of purchase must be between "
                + str(market_open.strftime("%I:%M %p"))
                + " and "
                + str(market_close.strftime("%I:%M %p"))
                + " on "
                + str(date.strftime("%m/%d/%Y"))
            )

        # Validate price: Price must be between the lowest and highest prices for the ticker on the given daTe
        price = self.cleaned_data.get("price")
        high = ticker_date_qset.first().high
        low = ticker_date_qset.first().low
        if not (low <= price <= high):
            raise forms.ValidationError(
                "Invalid stock price: Price must be between $"
                + str(low)
                + " and $"
                + str(high)
                + " on "
                + str(date.strftime("%m/%d/%Y"))
            )

        # Validate BUY: User cannot buy stock worth more than the value of cash in user's account at the time of purchase
        action = self.cleaned_data.get("action")
        quantity = self.cleaned_data.get("quantity")
        if action == "buy":
            valid_buy = _validate_cash_is_available(
                date, time, price, quantity, self.profile
            )
            if not valid_buy:
                raise forms.ValidationError(
                    "Invalid BUY: There is not enough cash in your account on the given date/time to complete this transaction"
                )

        # Validate SELL: User can't sell more shares than user owned on the date/time of sale
        else:
            valid_sell = _validate_shares_are_available(
                date, time, ticker, quantity, self.profile
            )
            if not valid_sell:
                raise forms.ValidationError(
                    "Invalid SELL: There are not enough shares of "
                    + str(ticker)
                    + " in your account on the given date/time to complete this transaction"
                )

        return cleaned_data

    def clean_action(self):
        action = self.cleaned_data.get("action")
        valid_action = _validate_action(action, ["buy", "sell"])
        if not valid_action:
            raise forms.ValidationError(
                "Invalid action: Stock transactions must be BUY or SELL"
            )
        return action

    def clean_date(self):
        date = self.cleaned_data.get("date")
        valid_date = _validate_date_not_in_future(date)
        if not valid_date:
            raise forms.ValidationError("Invalid date: Date cannot be in the future")
        return date

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")
        if quantity <= 0:
            raise forms.ValidationError(
                "Invalid number of shares: Quantity must be strictly positive"
            )
        return quantity

    def clean_price(self):
        price = self.cleaned_data.get("price")
        valid_price = _validate_price_is_positive(price)
        if not valid_price:
            raise forms.ValidationError(
                "Invalid price: Value must be strictly positive"
            )
        return price


class CashForm(forms.ModelForm):
    action = forms.CharField(widget=forms.Select(choices=CASH_ACTIONS))

    class Meta:
        model = Transaction
        fields = {"action", "date", "time", "price"}
        labels = {
            "action": "Transaction Type",
            "date": "Date",
            "time": "Time (ET)",
            "price": "Amount",
        }
        widgets = {
            "date": DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "time": TimeInput(attrs={"type": "time"}),
        }

    field_order = ["action", "date", "time", "price"]

    def __init__(self, *args, **kwargs):
        self.profile = kwargs.pop("profile")
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()

        # Validate time: Transaction cannot be in the future
        date = self.cleaned_data.get("date")
        time = self.cleaned_data.get("time")
        valid_time = _validate_time_not_in_future
        if not valid_time:
            raise forms.ValidationError(
                "Invalid time: Time cannot be in the future if the transaction date is today"
            )

        # Validate WITHDRAW: User cannot withdraw more money than is in user's account on the date/time of transaction
        action = self.cleaned_data.get("action")
        price = self.cleaned_data.get("price")

        if action == "withdraw":
            valid_withdraw = _validate_cash_is_available(
                date, time, price, 1, self.profile
            )
            if not valid_withdraw:
                raise forms.ValidationError(
                    "Invalid WITHDRAW: There is not enough cash in your account on the given date/time to complete this transaction"
                )

        return cleaned_data

    def clean_action(self):
        action = self.cleaned_data.get("action")
        valid_action = _validate_action(action, ["deposit", "withdraw"])
        if not valid_action:
            raise forms.ValidationError(
                "Invalid action: Cash transactions must be DEPOSIT or WITHDRAW"
            )
        return action

    def clean_date(self):
        date = self.cleaned_data.get("date")
        valid_date = _validate_date_not_in_future(date)
        if not valid_date:
            raise forms.ValidationError("Invalid date: Date cannot be in the future")
        return date

    def clean_price(self):
        price = self.cleaned_data.get("price")
        valid_price = _validate_price_is_positive(price)
        if not valid_price:
            raise forms.ValidationError(
                "Invalid amount: Value must be strictly positive"
            )
        return price
