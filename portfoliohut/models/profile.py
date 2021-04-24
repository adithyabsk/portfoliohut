from collections import defaultdict
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf
from django.contrib.auth.models import User
from django.db import models
from django.db.models import CharField, F, QuerySet, Value
from django.db.models.fields import DateField
from django.db.models.functions import Cast
from django.utils.timezone import now

from portfoliohut.finance import get_current_prices

from .transactions import Stock

PROFILE_TYPE_ACTIONS = (
    ("public", "PUBLIC"),
    ("private", "PRIVATE"),
)


# TODO (@eab148): Make sure that input dates for stocks are not before January 1st, 2000
#                 or, we need to amend this algorithm
def _build_stock_lookup(
    tickers_qset: QuerySet[str], start_date: Optional[str] = "2000-01-01"
) -> pd.DataFrame:
    """Generate a lookup table with daily stock prices for a given portfolio.

    The dataframe index will have the dates and the columns will be the tickers.

                TSLA GOOG AAPL
    2021-01-01  200  1232 123
    2021-01-02  212  1233 100
    ...
    2021-03-28  ...

    tickers: A queryset of valid tickers
    start_date: The start date of the yfinance lookup

    Return:
        prices_df (pd.DataFrame)

    """
    # We append the data horizontally so that the uneven rows get back filled with NaNs
    # automatically when we transpose the dataframe.
    ticker_prices = []
    for tic in tickers_qset:
        ticker_org_data = yf.Ticker(tic).history(start=start_date, interval="1d")
        ticker_prices.append(ticker_org_data["Close"])

    prices_df = pd.DataFrame(data=ticker_prices).T
    prices_df.columns = list(tickers_qset)
    prices_df.index.name = "date"
    prices_df.index = prices_df.index.normalize()

    # Handle edge case where "today" is the weekend but the data only exists up to Friday
    last_date = prices_df.index[-1]
    if now().date() > last_date:
        append_idx = pd.date_range(
            start=last_date + pd.Timedelta(days=1), end=now().date(), freq="D"
        )
        append_cols = prices_df.columns
        data = np.empty(
            (
                len(append_idx),
                len(append_cols),
            )
        )
        data[:] = prices_df.iloc[-1] * len(append_idx)
        prices_df = prices_df.append(
            pd.DataFrame(data=data, columns=append_cols, index=append_idx)
        )

    # Resample the dataframe to fill last known prices on days when the stock market is closed
    prices_df = prices_df.resample("D").ffill()

    return prices_df


def _calc_returns(stock_qset: "QuerySet[Stock]", stock_lookup: pd.DataFrame):
    """Compute the returns for a given query set of of stock transactions.

    Assumes that the qset is ordered by increasing dates.

    Args:
        stock_qset: A queryset of stock transactions
        stock_lookup: Output of `_build_stock_lookup`, a lookup table of tickers and prices on each
            date.

    Returns:
        pd.Series: returns percentages with `pd.DateTimeIndex` as indices

    """
    # Strip timezone and just get the date
    # all timezones are UTC so we don't need that information in here
    start_date = stock_qset.first().date_time.replace(tzinfo=None).date()
    today = now().date()
    date_range = pd.date_range(start=start_date, end=today, freq="D").date.tolist()
    portfolio = defaultdict(int)
    returns = []
    prev_balance = None
    sale_cash = 0

    # Don't need to convert this to a set since the query set supports the in operation
    stock_qset = stock_qset.annotate(date_only=Cast("date_time", DateField()))
    portfolio_dates_set = stock_qset.values_list("date_only", flat=True).distinct()

    # Assume that the balance and tickers are validated and you never
    # over extend yourself. Also does not take into account purchasing
    # on margin.

    # We don't care about cash withdrawals or deposits but we do care about money that is earned
    # through sales, we should keep that in our balances from a returns perspective.
    for date in date_range:
        cash_mod = 0
        if date in portfolio_dates_set:
            # Update portfolio
            stock_on_date_qset = stock_qset.filter(date_only=date)
            for stock in stock_on_date_qset:
                # Add shares if buying otherwise subtract shares
                share_count = stock.quantity * (1 if stock.action == "buy" else -1)
                portfolio[stock.ticker] += share_count
                if stock.action == "sell":  # selling locks in gains
                    cash_mod += float(stock.quantity * stock.price)

        # sale cash is all amount total sold
        # cash mod handles current amount sold
        sale_cash += cash_mod

        # Base case for when no stock actions have been taken yet
        if len(portfolio) == 0 and sale_cash == 0:
            returns.append(np.nan)
            continue

        # Compute updated balance
        curr_balance = (
            sum(
                [
                    shares
                    * stock_lookup.loc[
                        date.isoformat(), ticker
                    ]  # price (on that day) * quantity
                    for ticker, shares in portfolio.items()
                ]
            )
            + sale_cash
        )
        curr_return = np.nan
        # If cashmod is zero this is the standard returns calculation, but if you sold stock, then
        # we "lock-in" those gains into the returns calculation
        if prev_balance is not None:
            curr_return = (curr_balance - (prev_balance + cash_mod)) / (
                prev_balance + cash_mod
            )

        returns.append(curr_return)
        prev_balance = curr_balance

    rslt = pd.Series(returns, date_range, name="Returns")

    # If the results are all null, then we can just return an empty series
    nonzero_ser = rslt[(rslt != 0) & ~rslt.isnull()]
    if len(nonzero_ser) > 0:
        return rslt.loc[nonzero_ser.index[0] :]
    else:
        return pd.Series([], name="Returns")  # emtpy


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
        stocks_qset = self.stock_set.order_by("date_time")

        # EVIE'S ADDITIONS
        if len(stocks_qset) == 0:
            return pd.Series()

        # We need order_by here because SQL is finicky
        # https://stackoverflow.com/a/10849214/3262054
        tickers = (
            stocks_qset.order_by("ticker").values_list("ticker", flat=True).distinct()
        )
        prices_df = _build_stock_lookup(tickers)
        returns_series = _calc_returns(stocks_qset, prices_df)

        return returns_series

    def get_cumulative_returns(self) -> pd.Series:
        return (1 + self.get_returns_df()).cumprod() - 1

    def get_most_recent_return(self) -> float:
        returns = self.get_cumulative_returns()
        if not returns.empty:
            return self.get_cumulative_returns().iloc[-1]
        else:
            return float("nan")

    def get_portfolio_details(self):
        # we are not using a query set here because we need to compute the final portfolio from the
        # list of transactions which gives us something that is not a "django model"
        final_portfolio = defaultdict(int)
        # Query the database
        all_stock_transactions = self.stock_set.all()
        cash_balance = 0
        for transaction in all_stock_transactions:
            if transaction.action.upper() == "BUY":
                final_portfolio[transaction.ticker] += transaction.quantity
                cash_balance -= transaction.price * transaction.quantity
            else:
                final_portfolio[transaction.ticker] -= transaction.quantity
                cash_balance += transaction.price * transaction.quantity

        all_cash_transactions = self.cashbalance_set.all()
        for transaction in all_cash_transactions:
            if transaction.action.upper() == "DEPOSIT":
                cash_balance += transaction.value
            else:
                cash_balance -= transaction.value

        stocks, total = get_current_prices(final_portfolio)
        return stocks, total, cash_balance

    def table_query_sets(self):
        # Write logic for pagination and transactions table
        stock_transactions_table = self.stock_set.all().order_by("date_time")
        cash_transactions_table = self.cashbalance_set.all().order_by("date_time")

        cash_transactions_table = cash_transactions_table.annotate(
            price=F("value"), ticker=Value("--Cash--", output_field=CharField())
        ).values("price", "action", "date_time", "ticker")

        cash_transactions_table = cash_transactions_table.order_by("date_time")

        return stock_transactions_table, cash_transactions_table

    def top_stocks(self):
        stocks, total, _ = self.get_portfolio_details()
        sorted_stocks = sorted(stocks, key=lambda x: x.total_value, reverse=True)
        top_5_stocks = sorted_stocks[0:4]
        return top_5_stocks

    def __str__(self):
        return f"user={self.user.get_full_name()}"
