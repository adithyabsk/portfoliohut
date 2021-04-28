import io
import random
from datetime import datetime, timedelta

import pandas as pd
import pandas_market_calendars as mcal
import pytz
import yfinance as yf
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import BaseCommand
from django.db import transaction
from tqdm import tqdm

from portfoliohut.forms import CSVForm
from portfoliohut.models import Profile

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

    # Add stocks actions
    # this little algo buys the first N unique stocks and then the remaining M*2 stocks follow
    # a buy, sell pattern. Here M*2 must be less than N. The M stocks are selected in order of
    # appearance in the first N stocks.
    with transaction.atomic():
        initial_balance = 500_000.00
        column_names = ["action", "date", "time", "price", "ticker", "quantity"]
        rows = [
            [
                "deposit",
                datetime(year=2020, month=1, day=1).replace(tzinfo=TZ),
                "9:30",
                initial_balance,
                None,
                None,
            ]
        ]
        random.seed(seed * 100)
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
        stock_times = ["16:00"] * total_stocks
        stock_actions = ["buy"] * unique_ticker_count + ["sell", "buy"] * sell_buy_count
        # TODO: update this list comprehension to use `HistoricalEquity` for a speed increase
        stock_prices = [
            round(
                yf.Ticker(ticker)
                .history(start=date, end=date + timedelta(1), interval="1d")["Close"]
                .values[0],
                2,
            )
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
        rows += list(
            zip(
                stock_actions,
                stock_dates,
                stock_times,
                stock_prices,
                stock_tickers,
                stock_quantities,
            )
        )
        df = pd.DataFrame(rows, columns=column_names)
        df["date"] = pd.to_datetime(df["date"])
        output_stream = io.BytesIO()
        df.to_csv(output_stream, index=False, date_format="%Y-%m-%d")
        csv_file = SimpleUploadedFile.from_dict(
            {
                "filename": "temp.csv",
                "content": output_stream.getvalue(),
            }
        )
        csv_form = CSVForm(files={"csv_file": csv_file}, profile=profile)
        # the is_valid function does the actual checking and saving
        if not csv_form.is_valid():
            raise ValueError("The transaction data is invalid")


def load_demo_users():
    number_users = 3
    for i in tqdm(range(1, number_users + 1)):
        create_random_user(i)


class Command(BaseCommand):
    help = "Create fake data for portfoliohut."

    def handle(self, *args, **kwargs):
        load_demo_users()
