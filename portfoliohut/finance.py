"""Financial Helper functions"""
from collections import namedtuple
from typing import Dict, List, Tuple

import yfinance as yf

TickerDetail = namedtuple(
    "TickerDetail", ["ticker", "prices", "total_value", "website"]
)


def get_current_prices(stock_map: Dict[str, float]) -> Tuple[List[TickerDetail], float]:
    """Build a lookup table of the current prices for an input dictionary of stocks.

    Args:
        stock_map: The keys are tickers and the values are the the quantities.

    Returns:
        A tuple. The first item is a list of `TickerDetail`s and the second is the total value of
            all stocks in the portfolio.

    """
    total = 0
    result = []
    for ticker, quantity in stock_map.items():
        if quantity > 0:
            ticker_info = yf.Ticker(ticker).info
            ticker_price = ticker_info["regularMarketPreviousClose"]
            ticker_website = ticker_info["website"]
            ticker_detail = TickerDetail(
                ticker, ticker_price, ticker_price * quantity, ticker_website
            )
            total += ticker_detail.total_value
            result.append(ticker_detail)

    return result, total
