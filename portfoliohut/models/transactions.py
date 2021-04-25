from datetime import timedelta

import django_tables2 as tables
import pandas as pd
import pandas_market_calendars as mcal
import yfinance as yf
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class FinancialItem(models.Model):
    class FinancialActionType(models.TextChoices):
        EQUITY = "EQ", _("Equity")
        EXTERNAL_CASH = "EC", _("External Cash")
        INTERNAL_CASH = "IC", _("Internal Cash")

    class Meta:
        abstract = True

    type = models.CharField(
        max_length=4, blank=False, choices=FinancialActionType.choices
    )
    ticker = models.CharField(max_length=20, blank=False)  # For cash actions use "-"
    date = models.DateField(blank=False)

    def display_items(self):
        return [f"date={self.date}"]

    def __str__(self):
        return ", ".join(self.display_items())


CASH = (
    FinancialItem.FinancialActionType.EXTERNAL_CASH,
    FinancialItem.FinancialActionType.INTERNAL_CASH,
)


class Transaction(FinancialItem):
    """An individual transaction."""

    profile = models.ForeignKey(
        "portfoliohut.Profile", blank=False, on_delete=models.PROTECT
    )
    time = models.TimeField(blank=False)
    quantity = models.IntegerField(blank=False)  # positive for buy negative for sell
    price = models.DecimalField(
        max_digits=100,
        decimal_places=2,
        blank=False,
    )  # always greater than zero

    def display_items(self):
        items = super().display_items()
        items.append(f"profile={self.profile.user.get_full_name()}")
        if self.type == FinancialItem.FinancialActionType.EQUITY:
            items.extend([f"ticker={self.ticker}"])
        elif self.type in CASH:
            action = "deposit" if self.quantity > 0 else "withdrawal"
            items.append(f"{action}={self.price}")

        return items


class PortfolioItem(FinancialItem):
    """An item in a portfolio."""

    profile = models.ForeignKey(
        "portfoliohut.Profile", blank=False, on_delete=models.PROTECT
    )
    quantity = models.IntegerField(blank=False)  # positive for buy negative for sell
    price = models.DecimalField(
        max_digits=100,
        decimal_places=2,
        blank=False,
    )  # always greater than zero

    def display_items(self):
        items = super().display_items()
        items.append(f"profile={self.profile.user.get_full_name()}")
        if self.type == FinancialItem.FinancialActionType.EQUITY:
            items.extend([f"ticker={self.ticker}"])
        elif self.type in CASH:
            action = "deposit" if self.quantity > 0 else "withdrawal"
            items.append(f"{action}={self.price}")

        return items


class HistoricalEquityManager(models.Manager):
    def _add_historical_ticker_data(self, ticker: str, df: pd.DataFrame):
        if not df.empty:
            df = df.reset_index()
            self.bulk_create(
                [
                    self.model(
                        type=FinancialItem.FinancialActionType.EQUITY,
                        ticker=ticker,
                        date=record["Date"],
                        open=record["Open"],
                        high=record["High"],
                        low=record["Low"],
                        close=record["Close"],
                        volume=record["Volume"],
                        dividends=record["Dividends"],
                        stock_splits=record["Stock Splits"],
                    )
                    for record in df.to_dict("records")
                ]
            )

    def get_ticker(self, ticker):
        # First check if the ticker exists
        ticker_qset = self.filter(ticker=ticker)
        if ticker_qset.exists():
            # Check if we need to update the data in the table (default ordering is ascending dates)
            most_recent_date = ticker_qset.last().date
            today = timezone.now()
            if today.date() > most_recent_date:
                # Assume NYSE exchange (for now)
                nyse = mcal.get_calendar("NYSE")
                # The schedule is on the range [start_date, end_date] (inclusive)
                nyse_schedule = nyse.schedule(
                    start_date=today.date() - timedelta(days=1),
                    end_date=today.date() + timedelta(days=1),
                )
                if nyse.open_at_time(nyse_schedule, today):
                    # Get the most recent ticker prices
                    df = yf.Ticker(ticker).history(
                        start=most_recent_date + timedelta(days=1)
                    )
                    self._add_historical_ticker_data(ticker, df)

                    # return updated qset
                    return self.filter(ticker=ticker)

            # return original qset
            return ticker_qset
        else:
            df = yf.Ticker(ticker).history(period="max")
            self._add_historical_ticker_data(ticker, df)

            return self.filter(ticker=ticker)


class HistoricalEquity(FinancialItem):
    """Hold the history of a particular equity over time."""

    class Meta:
        ordering = ("date",)
        unique_together = (
            "ticker",
            "date",
        )

    objects = HistoricalEquityManager()
    open = models.DecimalField(max_digits=100, decimal_places=2, blank=False)
    high = models.DecimalField(max_digits=100, decimal_places=2, blank=False)
    low = models.DecimalField(max_digits=100, decimal_places=2, blank=False)
    close = models.DecimalField(max_digits=100, decimal_places=2, blank=False)
    volume = models.IntegerField()
    dividends = models.DecimalField(max_digits=100, decimal_places=2)
    stock_splits = models.IntegerField()

    def display_items(self):
        items = super().display_items()
        if self.type == FinancialItem.FinancialActionType.EQUITY:
            items.extend([f"ticker={self.ticker}"])

        return items


class EquityInfo(models.Model):
    ticker = models.CharField(max_length=20, blank=False)
    logo_url = models.URLField(blank=False)
    # Add other attributes from yf.Ticker().info as needed

    def __str__(self):
        return f"ticker={self.ticker}"


class PortfolioReturn(models.Model):
    """The rolling return on a particular day for a portfolio"""

    profile = models.ForeignKey("portfoliohut.Profile", on_delete=models.PROTECT)
    date_time = models.DateTimeField()
    floating_return = models.FloatField()

    def __str__(self):
        return f"profile={self.profile}, floating_return={self.floating_return:.2f}"


class TransactionTable(tables.Table):
    """
    This class is a helper class used by django_tables2. The library can
    convert a DB table to a HTML table based on the input model. This
    Columns can be customized with respect to user requirements. i.e no ID
    displayed in this table.
    Has in built pagination feature as well.
    """

    class Meta:
        model = Transaction
        sequence = (
            "type",
            "ticker",
            "price",
            "quantity",
            "date",
            "time",
        )
        exclude = (
            "profile",
            "id",
        )
        attrs = {"width": "160%"}
