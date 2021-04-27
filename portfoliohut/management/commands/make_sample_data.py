import random
from datetime import datetime, timedelta

import pandas as pd
import pandas_market_calendars as mcal
import pytz
import yfinance as yf
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.management import BaseCommand
from django.db import models, transaction
from django.db.models import F, Sum
from tqdm import tqdm

from portfoliohut.models import FinancialActionType, Profile, Transaction
from portfoliohut.models.transactions import CASH

TZ = pytz.timezone("UTC")
tech_stock_list = [
    "AAPL",
    "ADI",
    "ADP",
    "ADSK",
    "BABA",
    "BR",
    "CRM",
    "FB",
    "IBM",
    "MA",
    "MSFT",
    "MSI",
    "NVDA",
    "PYPL",
    "TTWO",
    "V",
    "VRSN",
    "XLNX",
]


def create_random_user(seed: int):
    """Create data for a demo user.

    Username and password are demo{seed}.

    The stock algo buys the first N unique stocks and then the remaining M*2 stocks follow a buy,
    sell pattern. Here M*2 must be less than N. The M stocks are selected in order of appearance in
    the first N stocks.

    """
    # Create Demo User
    with transaction.atomic():
        user = User.objects.create(
            username=f"demo{seed}",
            email=f"demo{seed}@example.com",
            password=make_password(f"demo{seed}"),
            first_name=f"Jane{seed}",
            last_name=f"Doe{seed}",
        )
        user.save()

    # Create Demo Profile
    with transaction.atomic():
        profile = Profile(user=user)
        profile.save()

    # Add Deposit
    initial_balance = 1_000_000.00
    with transaction.atomic():
        transaction_date = datetime(
            year=2020, month=1, day=1, hour=16, minute=0, tzinfo=TZ
        )
        # Don't really want to update the portfolioitem_set here yet, so we don't use the manager
        # methods
        Transaction(
            profile=profile,
            type=FinancialActionType.EXTERNAL_CASH,
            date=transaction_date.date(),
            time=transaction_date.time(),
            price=initial_balance,
            quantity=1,
        ).save()

    # Add stocks actions
    with transaction.atomic():
        # this little algo buys the first N unique stocks and then the remaining M*2 stocks follow
        # a buy, sell pattern. Here M*2 must be less than N. The M stocks are selected in order of
        # appearance in the first N stocks.
        random.seed(seed)
        unique_ticker_count = 6
        sell_buy_count = 2
        total_stocks = unique_ticker_count + 2 * sell_buy_count
        # Randomly pick stock tickers and repeat some of them for more buying and selling
        stock_tickers = random.choices(tech_stock_list, k=unique_ticker_count)
        stock_tickers += stock_tickers[: 2 * sell_buy_count]
        # Pick stock dates using the nyse to make sure that they are valid
        nyse = mcal.get_calendar("NYSE")
        stock_dates = sorted(
            pd.to_datetime(
                random.choices(
                    nyse.valid_days(start_date="2020-01-01", end_date="2020-12-31"),
                    k=unique_ticker_count + sell_buy_count * 2,
                )
            ).to_pydatetime()
        )
        stock_dates = [sd.replace(tzinfo=TZ) for sd in stock_dates]
        stock_actions = [1] * unique_ticker_count + [-1, 1] * sell_buy_count
        stock_prices = [
            yf.Ticker(ticker)
            .history(start=date, end=date + timedelta(1), interval="1d")["Close"]
            .values[0]
            for ticker, date in zip(
                stock_tickers + stock_tickers[: sell_buy_count * 2], stock_dates
            )
        ]
        stock_quantities = [
            max(
                round(initial_balance * (1 / (total_stocks + sell_buy_count)) / price),
                1,
            )
            for price in stock_prices[:unique_ticker_count]
        ]
        # buy or sell half of current holdings
        stock_quantities += list(
            map(lambda x: int(x / 2), stock_quantities[: sell_buy_count * 2])
        )
        transaction_list = []
        for st, sd, sa, sq, sp in zip(
            stock_tickers, stock_dates, stock_actions, stock_quantities, stock_prices
        ):
            # TODO: This might still be broken. It makes sense to use the validation code to add the
            #       data into the DB once that is merged in.
            # stock action
            transaction_list.append(
                Transaction(
                    profile=profile,
                    ticker=st,
                    type=FinancialActionType.EQUITY,
                    date=sd.date(),
                    time=sd.time(),
                    price=sp,
                    quantity=sq * sa,
                )
            )
            # cash action
            transaction_list.append(
                Transaction(
                    profile=profile,
                    ticker="-",
                    type=FinancialActionType.INTERNAL_CASH,
                    date=sd.date(),
                    time=sd.time(),
                    price=abs(sp * sq),
                    quantity=-sa,  # if sale balance goes up, for purchase balance goes down
                )
            )
        Transaction.objects.bulk_create(transaction_list, profile=profile)

        # Check to make sure that profile balance is greater than 0 (otherwise you overspent)
        assert (
            Transaction.objects.filter(profile=profile, type__in=CASH).aggregate(
                total=Sum(
                    F("price") * F("quantity"), output_field=models.DecimalField()
                )
            )["total"]
            > 0
        )


def load_demo_users():
    number_users = 3
    for i in tqdm(range(1, number_users + 1)):
        create_random_user(i)


class Command(BaseCommand):
    help = "Create fake data for portfoliohut."

    def handle(self, *args, **kwargs):
        load_demo_users()
