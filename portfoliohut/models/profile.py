from datetime import datetime
from decimal import Decimal

import pandas as pd
from django.contrib.auth.models import User
from django.db import models
from django.db.models import F, QuerySet, Sum, Window
from django.db.models.functions import Abs, Exp, Ln

from .transactions import (
    CashActions,
    FinancialActionType,
    HistoricalEquity,
    Transaction,
)

PROFILE_TYPE_ACTIONS = (
    ("public", "PUBLIC"),
    ("private", "PRIVATE"),
)


def _calc_returns(transaction_qset: "QuerySet[Transaction]"):
    """Compute the returns for a given query set of of stock transactions.

    Assumes that the qset is ordered by increasing dates.

    Args:
        transaction_qset: A queryset of stock transactions

    Returns:
        pd.Series: returns percentages with `pd.DateTimeIndex` as indices

    """

    # TODO: This won't work for multiple stock transactions of a single stock on the same day. I
    #       need to find a solution for this case. This will likely involve a step where I combine
    #       all stocks actions from a single day into a single row. (@adithysbk)

    # Filter for just internal cash transactions and equity transactions, then make sure to filter
    # out all of the buy actions. This is NOT actually your portfolio value but respects the
    # "locked" in gains
    relevant_transaction_qset = transaction_qset.filter(
        type__in=[
            FinancialActionType.EQUITY,
            FinancialActionType.INTERNAL_CASH,
        ]
    ).exclude(type=FinancialActionType.INTERNAL_CASH, quantity__lt=0)

    # Abort if there were no relevant transactions
    empty_series = pd.Series([], name="Returns")
    if not relevant_transaction_qset.exists():
        return empty_series

    start_date = relevant_transaction_qset.first().date_time.date()
    # Remove cash balance ticker
    distinct_tickers = set(
        relevant_transaction_qset.filter(type=FinancialActionType.EQUITY).values_list(
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
            *relevant_transaction_qset.filter(ticker=ticker).values_list(
                "date_time__date", "quantity"
            )
        )
        # Note: this is where the bug is
        # Sum the stocks bought on the same day
        quantity_series = pd.Series(quantities, index=dates, dtype="int64", name=ticker)
        quantity_series_list.append(
            quantity_series.groupby(quantity_series.index).sum()
        )
    quantities_df = (
        pd.concat(quantity_series_list, axis=1)
        .sort_index()
        .fillna(0)
        .cumsum()
        .reindex(stocks_df.index, method="ffill")
        .astype("int64")
    )

    # Also build the cumulative sale cash balance at each date.
    sale_cash_qset = relevant_transaction_qset.filter(
        type=FinancialActionType.INTERNAL_CASH
    ).values_list("date_time__date", "price")
    if sale_cash_qset.exists():
        sale_dates, sale_prices = zip(*sale_cash_qset)
        sale_cash_series = pd.Series(sale_prices, index=sale_dates, name="Cash")
        # Handle multiple sales on a single day (note this doesn't have the
        # same potential bug as above)
        sale_cash_series = (
            sale_cash_series.groupby(sale_cash_series.index)
            .sum()
            .cumsum()
            .reindex(stocks_df.index, method="ffill")
            .fillna(0)
            .astype(float)
        )
    else:
        sale_cash_series = pd.Series(
            [0] * len(quantities_df), index=stocks_df.index, name="Cash"
        )

    # Now, we simply multiply stocks_df by quantities_df and add sale_cash_df
    returns_series = stocks_df.multiply(quantities_df).sum(axis=1).add(sale_cash_series)
    returns_series.name = "Returns"
    returns_series = returns_series.dropna().pct_change()

    return returns_series


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name="profile")
    bio = models.CharField(max_length=240, default="Hello! I'm new to Portfolio Hut.")
    profile_type = models.CharField(
        max_length=7, choices=PROFILE_TYPE_ACTIONS, default="public"
    )
    friends = models.ManyToManyField("Profile", blank=True, related_name="friends_list")
    friend_requests = models.ManyToManyField(
        "Profile", blank=True, related_name="friend_requests_list"
    )

    # https://www.sqlservercentral.com/forums/topic/aggregate-function-product#post-1442921
    def get_cumulative_returns(self):
        # Original Pandas: (1 + self.get_returns_df()).cumprod() - 1
        return (
            self.portfolioreturn_set.values("date", "returns")
            .annotate(
                # Log-sum-exp trick reversed to get the cumulative product (https://en.wikipedia.org/wiki/LogSumExp)
                # Day to day returns cannot be lower than zero when you add 1 (i.e. gains are infinite losses are capped)
                # This is why we don't need to account for the sign here
                cumprod=Exp(
                    Window(Sum(Ln(Abs(F("returns") + 1))), order_by=F("date").asc())
                )
                - 1
            )
            .values("date", "cumprod")
        )

    def get_most_recent_return(self) -> float:
        most_recent_return = self.get_cumulative_returns().last()
        if most_recent_return is not None:
            return most_recent_return["cumprod"]
        else:
            return 0

    def is_cash_available(self, date_time: datetime, value: Decimal) -> bool:
        """Validate if `Profile` contains enough balance to fund a transaction on a particular date.

        Args:
            date_time: The date of the transaction
            value: The cost of the transaction

        """
        cash_transactions = self.transaction_set.filter(
            type__in=CashActions,
            date_time__lte=date_time,
        )

        if not cash_transactions.exists():
            return False

        cash_at_time = cash_transactions.aggregate(
            available_cash=Sum(
                F("price") * F("quantity"), output_field=models.DecimalField()
            )
        )["available_cash"]

        return cash_at_time >= value

    def is_shares_available(
        self, date_time: datetime, ticker: str, quantity: int
    ) -> bool:
        """Validate if Profile has enough shares for a sell action on a particular date.

        Args:
            date_time: The date/time of the transaction
            ticker: The stock's ticker
            quantity: The number of shares to be sold

        """
        stock_transactions = self.transaction_set.filter(
            ticker=ticker, date_time__lte=date_time
        )

        if not stock_transactions.exists():
            return False

        num_shares = stock_transactions.aggregate(sum=Sum("quantity"))["sum"]

        return num_shares >= quantity

    def is_duplicate_transaction(self, date_time: datetime.date, ticker: str):
        """Check if `Profile` contains a matching transaction"""
        return self.transaction_set.filter(date_time=date_time, ticker=ticker).exists()

    # def get_portfolio_details(self):
    #     # we are not using a query set here because we need to compute the final portfolio from the
    #     # list of transactions which gives us something that is not a "django model"
    #     final_portfolio = defaultdict(int)
    #     # Query the database
    #     all_transactions = self.transaction_set.all()
    #     cash_balance = 0
    #     for transaction in all_stock_transactions:
    #         if transaction.action.upper() == "BUY":
    #             final_portfolio[transaction.ticker] += transaction.quantity
    #             cash_balance -= transaction.price * transaction.quantity
    #         else:
    #             final_portfolio[transaction.ticker] -= transaction.quantity
    #             cash_balance += transaction.price * transaction.quantity
    #
    #     all_cash_transactions = self.cashbalance_set.all()
    #     for transaction in all_cash_transactions:
    #         if transaction.action.upper() == "DEPOSIT":
    #             cash_balance += transaction.value
    #         else:
    #             cash_balance -= transaction.value
    #
    #     stocks, total = get_current_prices(final_portfolio)
    #     return stocks, total, cash_balance

    # def table_query_sets(self):
    #     # Write logic for pagination and transactions table
    #     stock_transactions_table = self.stock_set.all().order_by("date_time")
    #     cash_transactions_table = self.cashbalance_set.all().order_by("date_time")
    #
    #     cash_transactions_table = cash_transactions_table.annotate(
    #         price=F("value"), ticker=Value("--Cash--", output_field=CharField())
    #     ).values("price", "action", "date_time", "ticker")
    #
    #     cash_transactions_table = cash_transactions_table.order_by("date_time")
    #
    #     return stock_transactions_table, cash_transactions_table

    # def top_stocks(self):
    #     stocks, total, _ = self.get_portfolio_details()
    #     sorted_stocks = sorted(stocks, key=lambda x: x.total_value, reverse=True)
    #     top_5_stocks = sorted_stocks[0:4]
    #     return top_5_stocks

    def __str__(self):
        return f"user={self.user.get_full_name()}"
