import random
from datetime import datetime, timedelta

import pandas as pd
import pandas_market_calendars as mcal
import pytz
import yfinance as yf
from django.contrib.auth.hashers import make_password
from django.db import migrations, transaction

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


def create_random_user(seed: int, User, Profile, CashBalance, Stock):
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

    # Add Cash Balance
    initial_balance = 100_000.00
    with transaction.atomic():
        cb_action = "deposit"
        cb_date = datetime(year=2020, month=1, day=1, tzinfo=TZ)
        cb_value = initial_balance
        CashBalance(
            profile=profile, action=cb_action, date_time=cb_date, value=cb_value
        ).save()

    # Add stocks actions
    with transaction.atomic():
        # this little algo buys the first N unique stocks and then the remaining M*2 stocks follow
        # a buy, sell pattern. Here M*2 must be less than N. The M stocks are selected in order of
        # appearance in the first N stocks.
        random.seed(seed)
        unique_ticker_count = 6
        sell_buy_count = 2
        stock_tickers = random.choices(tech_stock_list, k=unique_ticker_count)
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
        stock_actions = ["buy"] * unique_ticker_count + ["sell", "buy"] * sell_buy_count
        stock_prices = [
            yf.Ticker(ticker)
            .history(start=date, end=date + timedelta(1), interval="1d")["Close"]
            .values[0]
            for ticker, date in zip(
                stock_tickers + stock_tickers[: sell_buy_count * 2], stock_dates
            )
        ]
        stock_quantities = [
            max(round((initial_balance / 2) / price), 1)
            for price in stock_prices[:unique_ticker_count]
        ]
        # buy or sell half of current holdings
        stock_quantities += list(
            map(lambda x: x / 2, stock_quantities[: sell_buy_count * 2])
        )
        for st, sd, sa, sq, sp in zip(
            stock_tickers, stock_dates, stock_actions, stock_quantities, stock_prices
        ):
            Stock(
                profile=profile,
                ticker=st,
                action=sa,
                date_time=sd,
                price=sp,
                quantity=sq,
            ).save()


def load_demo_user(apps, schema_editor):
    number_users = 2
    User = apps.get_model("auth", "User")
    Profile = apps.get_model("portfoliohut", "Profile")
    CashBalance = apps.get_model("portfoliohut", "CashBalance")
    Stock = apps.get_model("portfoliohut", "Stock")
    for i in range(1, number_users + 1):
        create_random_user(i, User, Profile, CashBalance, Stock)


class Migration(migrations.Migration):

    dependencies = [
        ("portfoliohut", "0003_auto_20210412_1413"),
    ]

    operations = [migrations.RunPython(load_demo_user)]
