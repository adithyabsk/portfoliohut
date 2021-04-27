import pandas as pd
import plotly.express as px
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from portfoliohut.models import Profile
from portfoliohut.tables import PortfolioItemTable


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

        # table = TransactionTable(profile.transactions)
        # table.paginate(page=request.GET.get("page", 1), per_page=25)

        # Build graph
        graph_data = profile.get_cumulative_returns()
        dates = []
        for d in list(graph_data.index):
            dates.append(d.strftime("%m/%d/%Y"))
        returns = pd.Series(list(graph_data))
        dates = pd.Series(list(graph_data.index))
        data = {"Date": dates, "Returns": returns}

        # TODO: Change hardcoded data
        s_p_returns = returns.multiply(10)
        data = pd.concat(data, axis=1)
        data["User"] = str(request.user.username)
        sp_data = {"Date": dates, "Returns": s_p_returns}
        sp_data = pd.concat(sp_data, axis=1)
        sp_data["User"] = "S&P 500"
        complete_data = pd.concat([data, sp_data], ignore_index=True)
        fig = px.line(complete_data, x="Date", y="Returns", color="User")
        fig.update_xaxes(
            rangeslider_visible=True,
            rangeselector=dict(
                buttons=list(
                    [
                        dict(count=1, label="1m", step="month", stepmode="backward"),
                        dict(count=6, label="6m", step="month", stepmode="backward"),
                        dict(count=1, label="YTD", step="year", stepmode="todate"),
                        dict(count=1, label="1y", step="year", stepmode="backward"),
                        dict(step="all"),
                    ]
                )
            ),
        )

        graph = fig.to_html(full_html=False)

        return render(
            request,
            "portfoliohut/portfolio.html",
            {
                "current_portfolio_table": current_portfolio_table,
                # "profile_table": stocks,
                "total": "${:,.2f}".format(100_000),  # TODO: FIXME
                # "table": table,
                # "transactions": transactions,
                "cash": "${:,.2f}".format(100_000),  # TODO: FIXME
                "graph": graph,
            },
        )
