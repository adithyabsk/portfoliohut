from itertools import chain

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from portfoliohut.models import Profile, StockTable


@login_required
def portfolio(request):
    """
    Call Yahoo finance for all the stocks that are present in the user's portfolio
    Call all the transactions of the current user profile.
    """
    if request.method == "GET":
        profile = get_object_or_404(Profile, user=request.user)

        stocks, total, cash_balance = profile.get_portfolio_details()

        stock_transactions_table, cash_transactions_table = profile.table_query_sets()
        records = chain(stock_transactions_table, cash_transactions_table)
        table = StockTable(records)
        table.paginate(page=request.GET.get("page", 1), per_page=25)

        graph_data = profile.get_cumulative_returns()
        dates = []
        for d in list(graph_data.index):
            dates.append(d.strftime("%m/%d/%Y"))
        returns = list(graph_data)

        return render(
            request,
            "portfoliohut/portfolio.html",
            {
                "profile_table": stocks,
                "total": "${:,.2f}".format(total),
                "table": table,
                "cash": "${:,.2f}".format(cash_balance),
                "graph_dates": dates,
                "graph_returns": returns,
            },
        )
