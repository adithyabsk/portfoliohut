from collections import defaultdict
from itertools import chain

import yfinance as yf
from django.contrib.auth.decorators import login_required
from django.db.models import CharField, F, Value
from django.shortcuts import get_list_or_404, get_object_or_404, render

from portfoliohut.models import CashBalance, Profile, Stock, StockTable


def get_current_prices(stock_map):
    """
    Lookup the current price using yfinance and then return a dictionary with
    current prices of the stock.
    """
    total = 0
    result = []
    for k, v in stock_map.items():
        if v > 0:
            ticker_details = []
            ticker_details.append(k)
            ticker_price = yf.Ticker(k)
            ticker_details.append(ticker_price.info["regularMarketPreviousClose"])
            stock_value = ticker_price.info["regularMarketPreviousClose"] * v
            total += stock_value
            ticker_details.append(round(stock_value, 2))
            result.append(ticker_details)

        else:
            continue

    return result, total


@login_required
def get_portfolio(request):
    """
    Call Yahoo finance for all the stocks that are present in the user's portfolio
    Call all the transactions of the current user profile.
    """
    if request.method == "GET":
        stock_map = defaultdict(int)
        # Query the database
        profile = get_object_or_404(Profile, user=request.user)
        all_stock_transactions = get_list_or_404(Stock, profile=profile)
        for transaction in all_stock_transactions:
            if transaction.action.upper() == "BUY":
                stock_map[transaction.ticker] += transaction.quantity
            else:
                stock_map[transaction.ticker] -= transaction.quantity

        all_cash_transactions = get_list_or_404(CashBalance, profile=profile)
        cash_balance = 0
        for transaction in all_cash_transactions:
            if transaction.action.upper() == "DEPOSIT":
                cash_balance += transaction.value
            else:
                cash_balance -= transaction.value

        stocks, total = get_current_prices(stock_map)

        # Write logic for pagination and transactions table
        stock_transactions_table = Stock.objects.filter(profile=profile).order_by(
            "date_time"
        )
        cash_transactions_table = CashBalance.objects.filter(profile=profile).order_by(
            "date_time"
        )

        cash_transactions_table = cash_transactions_table.annotate(
            price=F("value"), ticker=Value("--Cash--", output_field=CharField())
        ).values("price", "action", "date_time", "ticker")

        cash_transactions_table = cash_transactions_table.filter(
            profile=profile
        ).order_by("date_time")

        records = chain(stock_transactions_table, cash_transactions_table)

        table = StockTable(records)

        table.paginate(page=request.GET.get("page", 1), per_page=25)

        return render(
            request,
            "portfoliohut/portfolio.html",
            {
                "profile_table": stocks,
                "total": "${:,.2f}".format(total),
                "table": table,
                "cash": "${:,.2f}".format(cash_balance),
            },
        )
