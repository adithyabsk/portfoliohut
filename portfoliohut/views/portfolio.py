from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from portfoliohut.graph import _get_sp_index, combine_index_user, multi_plot
from portfoliohut.models import Profile
from portfoliohut.tables import PortfolioItemTable

NUM_TRANSACTIONS = 5


@login_required
def portfolio(request):
    """
    Call Yahoo finance for all the stocks that are present in the user's portfolio
    Call all the transactions of the current user profile.
    """
    if request.method == "GET":
        profile = get_object_or_404(Profile, user=request.user)

        # Get current portfolio
        current_portfolio_table = PortfolioItemTable(profile.portfolioitem_set.all())
        current_portfolio_table.paginate(
            page=request.GET.get("page", 1), per_page=NUM_TRANSACTIONS
        )

        # Build graph
        graph_data = profile.get_cumulative_returns()
        graph = None
        if not graph_data.empty:
            start_date = graph_data.index[0]
            index_data = _get_sp_index(start_date)
            merged_df = combine_index_user(graph_data, index_data)
            graph = multi_plot(merged_df)

        return render(
            request,
            "portfoliohut/portfolio.html",
            {
                "current_portfolio_table": current_portfolio_table,
                "graph": graph,
            },
        )
