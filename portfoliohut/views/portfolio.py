import math

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from portfoliohut.graph import _get_sp_index, combine_index_user, multi_plot
from portfoliohut.models import FinancialActionType, Profile
from portfoliohut.tables import PortfolioItemTable, TransactionTable

NUM_TRANSACTIONS = 10


@login_required
def returns_graph(request):
    profile = get_object_or_404(Profile, user=request.user)
    graph_data = profile.get_cumulative_returns().to_series() * 100
    graph = None
    if not graph_data.empty:
        start_date = graph_data.index[0]
        index_data = _get_sp_index(start_date)
        merged_df = combine_index_user(graph_data, index_data)
        graph = multi_plot(merged_df)
    return HttpResponse(graph)


@login_required
def portfolio(request):
    """
    Call Yahoo finance for all the stocks that are present in the user's portfolio
    Call all the transactions of the current user profile.
    """
    if request.method == "GET":
        profile = get_object_or_404(Profile, user=request.user)

        has_returns = True
        returns = profile.get_most_recent_return()
        if math.isnan(returns):
            has_returns = False

        # Get current portfolio
        current_portfolio_table = PortfolioItemTable(profile.portfolioitem_set.all())
        current_transactions_table = TransactionTable(
            profile.transaction_set.filter(
                type__in=[FinancialActionType.EXTERNAL_CASH, FinancialActionType.EQUITY]
            )
            .all()
            .order_by("-date_time")
        )
        current_transactions_table.paginate(
            page=request.GET.get("page", 1), per_page=NUM_TRANSACTIONS
        )

        return render(
            request,
            "portfoliohut/portfolio.html",
            {
                "has_returns": has_returns,
                "current_portfolio_table": current_portfolio_table,
                "current_transactions_table": current_transactions_table,
            },
        )
