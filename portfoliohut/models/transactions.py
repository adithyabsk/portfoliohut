from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, List

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import yfinance as yf
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import ExpressionWrapper, F, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from .profile import Profile


class FinancialActionType(models.TextChoices):
    EQUITY = "EQ", _("Equity")
    EXTERNAL_CASH = "EC", _("External Cash")
    INTERNAL_CASH = "IC", _("Internal Cash")


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

    def _recompute_returns(self, profile: "Profile"):
        """Compute the returns for a given query set of of stock transactions.

        Assumes that the qset is ordered by increasing dates.

        Args:
            profile: The profile for which to recompute the returns

        Returns:
            QuerySet[ReturnItem]

        """

        # TODO: We really don't need to recompute all returns every time a transaction is added, we
        #       recompute returns from that point in time. (@adithyabsk)

        # Filter for just internal cash transactions and equity transactions, then make sure to filter
        # out all of the buy actions. This is NOT actually your portfolio value but respects the
        # "locked" in gains
        profile_transactions = self.filter(profile=profile)
        # relevant_transaction_qset = self.filter(profile=profile).filter(
        #     type__in=[
        #         FinancialActionType.EQUITY,
        #         FinancialActionType.INTERNAL_CASH,
        #     ]
        # ).exclude(type=FinancialActionType.INTERNAL_CASH, quantity__lt=0)

        # Abort if there were no relevant transactions
        empty_series = pd.Series([], name="Returns")
        if not profile_transactions.exists():
            return empty_series

        start_date = profile_transactions.first().date_time.date()
        # Remove cash balance ticker
        distinct_tickers = set(
            profile_transactions.filter(type=FinancialActionType.EQUITY).values_list(
                "ticker", flat=True
            )
        )

        # Abort if there were not any stock transactions
        if not distinct_tickers:
            return empty_series

        # Build a list of stock prices across all relevant dates
        price_series_list = []
        for ticker in distinct_tickers:
            dates, closes = zip(
                *HistoricalEquity.objects.get_ticker(ticker)
                .filter(date__gte=start_date)
                .values_list("date", "close")
            )
            price_series_list.append(pd.Series(closes, index=dates, name=ticker))
        stocks_df = pd.concat(price_series_list, axis=1).sort_index()

        # Build a DataFrame similar to previous with the cumulative quantities at each date.
        # TODO: There is another bug here where the first day of returns may be calculated incorrectly
        #       since we use the close price to compute returns rather than the price that a user paid
        #       for the equity.
        quantity_series_list = []
        for ticker in distinct_tickers:
            dates, quantities = zip(
                *profile_transactions.filter(ticker=ticker).values_list(
                    "date_time__date", "quantity"
                )
            )
            # Note: this is where the bug is
            # Sum the stocks bought on the same day
            quantity_series = pd.Series(
                quantities, index=dates, dtype="int64", name=ticker
            )
            quantity_series_list.append(
                quantity_series.groupby(quantity_series.index).sum()
            )
        quantities_df = (
            pd.concat(quantity_series_list, axis=1)
            .sort_index()
            .fillna(0)
            .cumsum()
            .reindex(stocks_df.index, method="ffill")
            .fillna(0)
            .astype("int64")
        )

        # Build the cumulative internal cash at each date (buy/sell)
        internal_cash_qset = profile_transactions.filter(
            type=FinancialActionType.INTERNAL_CASH
        ).values_list(
            "date_time__date",
            ExpressionWrapper(
                F("price") * F("quantity"),
                output_field=models.DecimalField(decimal_places=2, max_digits=100),
            ),
        )
        if internal_cash_qset.exists():
            sale_dates, sale_prices = zip(*internal_cash_qset)
            internal_cash_series = pd.Series(sale_prices, index=sale_dates, name="Cash")
            internal_cash_series = (
                internal_cash_series.groupby(internal_cash_series.index)
                .sum()
                .cumsum()
                .reindex(stocks_df.index, method="ffill")
                .fillna(0)
                # .astype(float)
            )
        else:
            internal_cash_series = pd.Series(
                [0] * len(quantities_df), index=stocks_df.index, name="Cash"
            )

        # Build the discrete cash flows at each date (cash deposits and withdrawals)
        external_cash_qset = profile_transactions.filter(
            type=FinancialActionType.EXTERNAL_CASH
        ).values_list(
            "date_time__date",
            ExpressionWrapper(
                F("price") * F("quantity"),
                output_field=models.DecimalField(decimal_places=2, max_digits=100),
            ),
        )
        if external_cash_qset.exists():
            sale_dates, sale_prices = zip(*external_cash_qset)
            external_cash_series = pd.Series(sale_prices, index=sale_dates, name="Cash")
            external_cash_series = (
                external_cash_series.groupby(external_cash_series.index)
                .sum()
                .reindex(stocks_df.index, method=None)
                .fillna(0)
                # .astype(float)
            )
        else:
            external_cash_series = pd.Series(
                [0] * len(quantities_df), index=stocks_df.index, name="Cash"
            )

        # Compute time-weighted returns
        # https://rodgers-associates.com/blog/why-is-time-weighted-return-a-good-way-to-track-performance-in-retirement/
        # Now, we multiply stocks_df by quantities_df and add internal cash management
        partial_portval = (
            stocks_df.multiply(quantities_df)
            .sum(axis=1)
            .add(internal_cash_series.astype(float))
        )
        complete_portval = partial_portval + external_cash_series.cumsum().shift(
            1
        ).astype(float)
        comp_df = pd.DataFrame(
            {
                "bpv": complete_portval.shift(1),  # yesterday portfolio value
                "epv": complete_portval,  # today portfolio value
                "cf": external_cash_series,  # cash flow
            }
        ).dropna()
        twr_series = comp_df.apply(
            lambda row: (row.epv - (row.bpv + row.cf)) / (row.bpv + row.cf), axis=1
        )
        twr_series.name = "returns"
        twr_series.replace([np.inf, -np.inf], np.nan, inplace=True)
        twr_series = twr_series.dropna()

        with transaction.atomic():
            profile.portfolioreturn_set.all().delete()
            prs = PortfolioReturn.objects.bulk_create(
                [
                    PortfolioReturn(
                        profile=profile,
                        date=date,
                        returns=returns,
                    )
                    for date, returns in twr_series.iteritems()  # noqa: B301
                ]
            )

            return prs

    def _create_equity_transaction(self, **kwargs):
        # stock action
        with transaction.atomic():
            self.model(**kwargs).save()
            # cash action
            kwargs.pop("type")
            value = kwargs.pop("price") * kwargs.pop("quantity")
            kwargs.pop("ticker")
            # subtract money if buying and add money if selling
            quantity = -1 if value > 0 else 1
            self.model(
                ticker="-",
                price=abs(value),
                quantity=quantity,
                type=FinancialActionType.INTERNAL_CASH,
                **kwargs,
            ).save()

    def _create_cash_transaction(self, **kwargs):
        self.model(**kwargs).save()

    def post_add_transaction_steps(self, profile: "Profile"):
        self._reset_portfolio_cache(profile=profile)
        self._recompute_returns(profile=profile)

    def create_equity_transaction(self, only_create=False, **kwargs):
        self._create_equity_transaction(**kwargs)
        if not only_create:
            self.post_add_transaction_steps(profile=kwargs.get("profile"))

    def create_cash_transaction(self, only_create=False, **kwargs):
        self._create_cash_transaction(**kwargs)
        if not only_create:
            self.post_add_transaction_steps(profile=kwargs.get("profile"))

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


class Transaction(models.Model):
    """An individual transaction.

    You must use `Transaction.objects.create_equity_transaction` or `Transaction.objects.create_cash_transaction`
    so that the related `PortfolioItem` will be updated. Use bulk create along with the helper method
    `Transaction.objects._create_equity_transaction` to skip `PortfolioItem` after each `Transaction`
    creation.

    """

    class Meta:
        unique_together = ("profile", "ticker", "date_time")

    objects = TransactionManager()
    type = models.CharField(
        max_length=4, blank=False, choices=FinancialActionType.choices
    )
    ticker = models.CharField(max_length=20, blank=False)  # For cash actions use "-"
    profile = models.ForeignKey(
        "portfoliohut.Profile", blank=False, on_delete=models.PROTECT
    )
    date_time = models.DateTimeField(blank=False)
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
        items = [
            f"date={self.date_time}",
            f"profile={self.profile.user.get_full_name()}",
        ]
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

    def quantity_annotator(self):
        if self.quantity < 0:
            return "Sell"
        else:
            return "Buy"

    def __str__(self):
        return ", ".join(self.display_items())


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

    def viewable_type(self):
        if self.type == FinancialActionType.EXTERNAL_CASH:
            if self.quantity > 0:
                return "DEPOSIT"
            return "WITHDRAW"
        elif self.type == FinancialActionType.EQUITY:
            if self.quantity > 0:
                return "BUY"
            return "SELL"
        return ""

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


class HistoricalEquity(models.Model):
    """Hold the history of a particular equity over time."""

    class Meta:
        ordering = ("date",)
        unique_together = (
            "ticker",
            "date",
        )

    objects = HistoricalEquityManager()
    type = models.CharField(
        max_length=4, blank=False, choices=FinancialActionType.choices
    )
    ticker = models.CharField(max_length=20, blank=False)  # For cash actions use "-"
    date = models.DateField(blank=False)
    open = models.DecimalField(max_digits=100, decimal_places=2, blank=False)
    high = models.DecimalField(max_digits=100, decimal_places=2, blank=False)
    low = models.DecimalField(max_digits=100, decimal_places=2, blank=False)
    close = models.DecimalField(max_digits=100, decimal_places=2, blank=False)
    volume = models.PositiveBigIntegerField()
    dividends = models.DecimalField(max_digits=100, decimal_places=2)
    stock_splits = models.IntegerField()

    def display_items(self):
        items = [f"date={self.date}"]
        if self.type == FinancialActionType.EQUITY:
            items.extend([f"ticker={self.ticker}"])

        return items

    def __str__(self):
        return ", ".join(self.display_items())


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
    ticker = models.CharField(max_length=20, blank=False, unique=True)
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


class PortfolioReturnQuerySet(models.QuerySet):
    def to_series(self):
        qset = self.order_by("date").values_list("date", "returns")
        if qset.exists():
            dates, returns = zip(*self.order_by("date").values_list("date", "returns"))
            return pd.Series(returns, index=dates, name="returns")
        else:
            return pd.Series([], name="returns")


class PortfolioReturn(models.Model):
    """The rolling return on a particular day for a portfolio"""

    profile = models.ForeignKey(
        "portfoliohut.Profile", blank=False, on_delete=models.PROTECT
    )
    date = models.DateField(blank=False)
    returns = models.FloatField(blank=False)
    objects = PortfolioReturnQuerySet.as_manager()

    def __str__(self):
        return f"profile={self.profile}, floating_return={self.returns:.2f}"
