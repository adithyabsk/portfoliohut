from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, List

import django_tables2 as tables
import pandas as pd
import pandas_market_calendars as mcal
import yfinance as yf
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from .profile import Profile


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


FinancialActionType = FinancialItem.FinancialActionType
CashActions = (
    FinancialActionType.EXTERNAL_CASH,
    FinancialActionType.INTERNAL_CASH,
)


# TODO: Technically this can be optimized since we only really need to update the particular items
#       that were updated. We don't really need to delete all of the portfolio items. We just need
#       to recompute the particular ticker as well as the cash balance.
class TransactionManager(models.Manager):
    def _reset_portfolio_cache(self, profile: "Profile"):
        with transaction.atomic():
            # Delete previous snapshot
            profile.portfolioitem_set.all().delete()
            # Figure out current average price (group by ticker and then annotate weighted average price)
            item_dicts = (
                profile.transaction_set.filter(type=FinancialActionType.EQUITY)
                .values("ticker")
                .order_by("ticker")
                .annotate(
                    total_quantity=Sum("quantity"),
                    average_price=Sum(
                        (F("quantity") * F("price")), output_field=models.DecimalField()
                    )
                    / Sum("quantity", output_field=models.DecimalField()),
                )
            )
            PortfolioItem.objects.bulk_create(
                [
                    PortfolioItem(
                        profile=profile,
                        type=FinancialActionType.EQUITY,
                        ticker=d.get("ticker"),
                        quantity=d.get("total_quantity"),
                        price=d.get("average_price"),
                    )
                    for d in item_dicts
                ]
            )
            total_price = (
                profile.transaction_set.filter(type__in=CashActions)
                .values("quantity", "price")
                .aggregate(
                    total_price=Sum(
                        (F("quantity") * F("price")), output_field=models.DecimalField()
                    )
                )["total_price"]
            )
            PortfolioItem(
                ticker="-",
                profile=profile,
                type=FinancialActionType.EXTERNAL_CASH,
                quantity=1 if total_price > 0 else -1,
                price=abs(total_price),
            ).save()

    def _create_equity_transaction(self, **kwargs):
        # stock action
        with transaction.atomic():
            self.model(**kwargs).save()
            # cash action
            kwargs.pop("type")
            value = kwargs.pop("price") * kwargs.pop("quantity")
            # subtract money if buying and add money if selling
            quantity = -1 if value > 0 else 1
            self.model(
                price=abs(value),
                quantity=quantity,
                type=FinancialActionType.INTERNAL_CASH,
                **kwargs,
            ).save()

    def _create_cash_transaction(self, **kwargs):
        self.model(**kwargs).save()

    def create_equity_transaction(self, skip_portfolio_reset=False, **kwargs):
        self._create_equity_transaction(**kwargs)
        if not skip_portfolio_reset:
            self._reset_portfolio_cache(profile=kwargs.get("profile"))

    def create_cash_transaction(self, skip_portfolio_reset=False, **kwargs):
        self._create_cash_transaction(**kwargs)
        if not skip_portfolio_reset:
            self._reset_portfolio_cache(profile=kwargs.get("profile"))

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False, profile=None):
        objs: List[Transaction] = super().bulk_create(
            objs, batch_size=batch_size, ignore_conflicts=ignore_conflicts
        )
        if profile is None:
            pks = {}
            profiles = []
            for obj in objs:
                if obj.profile.pk not in pks:
                    profiles.append(obj.profile)
            for profile in profiles:
                self._reset_portfolio_cache(profile=profile)
        else:
            self._reset_portfolio_cache(profile=profile)


class Transaction(FinancialItem):
    """An individual transaction.

    You must use `Transaction.objects.create_equity_transaction` or `Transaction.objects.create_cash_transaction`
    so that the related `PortfolioItem` will be updated. Use bulk create along with the helper method
    `Transaction.objects._create_equity_transaction` to skip `PortfolioItem` after each `Transaction`
    creation.

    """

    objects = TransactionManager()
    profile = models.ForeignKey(
        "portfoliohut.Profile", blank=False, on_delete=models.PROTECT
    )
    time = models.TimeField(blank=False)
    quantity = models.IntegerField(
        blank=False
    )  # positive for buy/deposit negative for sell/withdraw
    price = models.DecimalField(
        max_digits=100,
        decimal_places=2,
        blank=False,
        validators=[MinValueValidator(Decimal("0.01"))],
    )  # always greater than zero

    def display_items(self):
        items = super().display_items()
        items.append(f"profile={self.profile.user.get_full_name()}")
        if self.type == FinancialActionType.EQUITY:
            items.append(f"ticker={self.ticker}")
        elif self.type == FinancialActionType.EXTERNAL_CASH:
            action = "cash_deposit" if self.quantity > 0 else "cash_withdrawal"
            items.append(f"{action}={self.price}")
        elif self.type == FinancialActionType.INTERNAL_CASH:
            action = "cash_sale" if self.quantity > 0 else "cash_purchase"
            items.append(f"{action}={self.price}")
            items.append(f"quantity={abs(self.quantity)}")

        return items


# Note: It made more sense for this to be its own class rather than for it to inherit from the base
#       class. This is because we want to auto add the date.
class PortfolioItem(models.Model):
    """An item in a portfolio."""

    profile = models.ForeignKey(
        "portfoliohut.Profile", blank=False, on_delete=models.PROTECT
    )
    # The type here can really only EQUITY or EXTERNAL_CASH
    type = models.CharField(
        max_length=4, blank=False, choices=FinancialActionType.choices
    )
    ticker = models.CharField(max_length=20, blank=False)  # For cash actions use "-"
    created = models.DateTimeField(auto_now_add=True)  # created datetime
    # For cash items
    quantity = models.IntegerField(
        blank=False
    )  # positive for buy/deposit negative for sell/withdraw
    price = models.DecimalField(
        max_digits=100,
        decimal_places=2,
        blank=False,
    )  # always greater than zero

    def total_value(self):
        return self.quantity * self.price

    def display_items(self):
        items = [f"profile={self.profile.user.get_full_name()}"]
        if self.type == FinancialActionType.EQUITY:
            items.extend([f"ticker={self.ticker}", f"average_price={self.price}"])
        elif self.type in CashActions:  # there is no
            items.append(f"balance={self.price*self.quantity}")

        return items

    def __str__(self):
        return ", ".join(self.display_items())


class HistoricalEquityManager(models.Manager):
    def _add_historical_ticker_data(self, ticker: str, df: pd.DataFrame):
        if not df.empty:
            df = df.reset_index()
            df = df.dropna(subset=["Open", "Close"])
            df = df.where(pd.notnull(df), None)
            self.bulk_create(
                [
                    self.model(
                        type=FinancialActionType.EQUITY,
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
            if not df.empty:
                self._add_historical_ticker_data(ticker, df)
                return self.filter(ticker=ticker)
            else:
                return HistoricalEquity.objects.none()


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
        if self.type == FinancialActionType.EQUITY:
            items.extend([f"ticker={self.ticker}"])

        return items


class EquityInfoManager(models.Manager):
    def get_ticker(self, ticker):
        try:
            return self.get(ticker=ticker)
        except ObjectDoesNotExist:
            ticker_info = yf.Ticker(ticker).info
            if "symbol" not in ticker_info:
                raise ObjectDoesNotExist(
                    f"could not find ticker '{ticker}' on yfinance"
                )
            ei = EquityInfo(
                ticker=ticker,
                logo_url=ticker_info.get("logo_url"),
                address1=ticker_info.get("address1"),
                city=ticker_info.get("city"),
                country=ticker_info.get("country"),
                zipcode=ticker_info.get("zip"),
                industry=ticker_info.get("industry"),
                sector=ticker_info.get("sector"),
                summary=ticker_info.get("longBusinessSummary"),
                name=ticker_info.get("longName"),
            )
            ei.save()

            return ei


class EquityInfo(models.Model):
    objects = EquityInfoManager()
    ticker = models.CharField(max_length=20, blank=False)
    logo_url = models.URLField(blank=False)

    address1 = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    country = models.CharField(max_length=255)
    zipcode = models.CharField(max_length=255)
    industry = models.CharField(max_length=255)
    sector = models.CharField(max_length=255)
    summary = models.TextField()
    name = models.CharField(max_length=255)

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
