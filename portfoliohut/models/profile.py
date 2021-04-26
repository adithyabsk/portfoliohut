import pandas as pd
from django.contrib.auth.models import User
from django.db import models
from django.db.models import CharField, F, QuerySet, Value

from .transactions import FinancialItem, HistoricalEquity, Transaction

PROFILE_TYPE_ACTIONS = (
    ("public", "PUBLIC"),
    ("private", "PRIVATE"),
)


def _calc_returns(transaction_qset: "QuerySet[Transaction]"):
    """Compute the returns for a given query set of of stock transactions.

    Assumes that the qset is ordered by increasing dates.

    Args:
        stock_qset: A queryset of stock transactions

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
            FinancialItem.FinancialActionType.EQUITY,
            FinancialItem.FinancialActionType.INTERNAL_CASH,
        ]
    ).exclude(type=FinancialItem.FinancialActionType.INTERNAL_CASH, quantity__lt=0)
    start_date = relevant_transaction_qset.first().date
    # Remove cash balance ticker
    distinct_tickers = set(
        relevant_transaction_qset.filter(
            type=FinancialItem.FinancialActionType.EQUITY
        ).values_list("ticker", flat=True)
    )

    if not distinct_tickers:
        return pd.Series([], name="Returns")

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
    quantity_series_list = []
    for ticker in distinct_tickers:
        dates, quantities = zip(
            *relevant_transaction_qset.filter(ticker=ticker).values_list(
                "date", "quantity"
            )
        )
        quantity_series_list.append(
            pd.Series(quantities, index=dates, dtype="int64", name=ticker)
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
    sale_dates, sale_prices = zip(
        *relevant_transaction_qset.filter(
            type=FinancialItem.FinancialActionType.INTERNAL_CASH
        ).values_list("date", "price")
    )
    sale_cash_series = (
        pd.Series(sale_prices, index=sale_dates, name="Cash")
        .cumsum()
        .reindex(stocks_df.index, method="ffill")
        .fillna(0)
        .astype(float)
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

    def get_returns_df(self) -> pd.Series:
        return _calc_returns(self.transaction_set)

    def get_cumulative_returns(self) -> pd.Series:
        return (1 + self.get_returns_df()).cumprod() - 1

    def get_most_recent_return(self) -> float:
        returns = self.get_cumulative_returns()
        if not returns.empty:
            return self.get_cumulative_returns().iloc[-1]
        else:
            return float("nan")

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

    def table_query_sets(self):
        # Write logic for pagination and transactions table
        stock_transactions_table = self.stock_set.all().order_by("date_time")
        cash_transactions_table = self.cashbalance_set.all().order_by("date_time")

        cash_transactions_table = cash_transactions_table.annotate(
            price=F("value"), ticker=Value("--Cash--", output_field=CharField())
        ).values("price", "action", "date_time", "ticker")

        cash_transactions_table = cash_transactions_table.order_by("date_time")

        return stock_transactions_table, cash_transactions_table

    # def top_stocks(self):
    #     stocks, total, _ = self.get_portfolio_details()
    #     sorted_stocks = sorted(stocks, key=lambda x: x.total_value, reverse=True)
    #     top_5_stocks = sorted_stocks[0:4]
    #     return top_5_stocks

    def __str__(self):
        return f"user={self.user.get_full_name()}"
