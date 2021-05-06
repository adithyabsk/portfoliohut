import io
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import pytz
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import BaseCommand
from django.db import transaction
from tqdm import tqdm

from portfoliohut.forms import CSVForm
from portfoliohut.models import HistoricalEquity, Profile

REPO_PATH = Path(__file__).parent / "../../.."

TZ = pytz.timezone("America/New_York")
tech_stock_list = pd.Series(
    [
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
)


def _save_dataframe(profile, df):
    output_stream = io.BytesIO()
    df.to_csv(output_stream, index=False)
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


def create_base_user_models(seed: int):
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

    return user, profile


def create_simple_user(seed: int):
    _, profile = create_base_user_models(seed)
    # Load simple sample data
    df = pd.read_csv(REPO_PATH / "portfoliohut/static/portfoliohut/sample_upload.csv")
    _save_dataframe(profile, df)


def create_complex_user(seed: int):
    """Create data for a demo user.

    Username and password are demo{seed}.

    The stock algo buys the first N unique stocks and then the remaining M*2 stocks follow a buy,
    sell pattern. Here M*2 must be less than N. The M stocks are selected in order of appearance in
    the first N stocks.

    """
    user, profile = create_base_user_models(seed)
    # Add stocks actions
    # this little algo buys the first N unique stocks and then the remaining M*2 stocks follow
    # a buy, sell pattern. Here M*2 must be less than N. The M stocks are selected in order of
    # appearance in the first N stocks.
    with transaction.atomic():
        # random.seed(seed * 100)
        np.random.seed(seed * 100)
        unique_ticker_count = 6
        sell_buy_count = 2
        total_stocks = unique_ticker_count + 2 * sell_buy_count
        # Randomly pick stock tickers and repeat some of them for more buying and selling
        stock_tickers = tech_stock_list.sample(unique_ticker_count).tolist()
        stock_tickers += stock_tickers[: 2 * sell_buy_count]
        # Pick stock dates using the nyse to make sure that they are valid
        nyse = mcal.get_calendar("NYSE")
        stock_date_times = (
            nyse.schedule(start_date="2020-01-01", end_date="2020-12-31")
            .market_close.dt.tz_convert(TZ)
            .sample(unique_ticker_count + sell_buy_count * 2)
            .sort_values()
            .dt.to_pydatetime()
        )
        stock_actions = ["buy"] * unique_ticker_count + ["sell", "buy"] * sell_buy_count
        # TODO: update this list comprehension to use `HistoricalEquity` for a speed increase
        stock_prices = [
            HistoricalEquity.objects.get_ticker(ticker)
            .filter(date=date_time.date())
            .first()
            .close
            for ticker, date_time in zip(
                stock_tickers + stock_tickers[: sell_buy_count * 2], stock_date_times
            )
        ]
        initial_balance = Decimal(500_000.00)
        stock_quantities = [
            max(round(initial_balance / total_stocks / price), 1)
            for price in stock_prices[:unique_ticker_count]
        ]
        # buy or sell half of current holdings
        stock_quantities += list(
            map(lambda x: int(x / 2), stock_quantities[: sell_buy_count * 2])
        )
        rows = [
            [
                "deposit",
                datetime(year=2020, month=1, day=2, hour=9, minute=30).replace(
                    tzinfo=TZ
                ),
                initial_balance,
                None,
                None,
            ]
        ]
        rows += list(
            zip(
                stock_actions,
                stock_date_times,
                stock_prices,
                stock_tickers,
                stock_quantities,
            )
        )
        column_names = ["action", "date_time", "price", "ticker", "quantity"]
        df = pd.DataFrame(rows, columns=column_names)
        _save_dataframe(profile, df)


def load_demo_users():
    number_users = 3
    for i in tqdm(range(1, number_users + 1)):
        create_complex_user(i)

    # number "4"
    create_simple_user(number_users + 1)


class Command(BaseCommand):
    help = "Create fake data for portfoliohut."

    def handle(self, *args, **kwargs):
        load_demo_users()
