# from datetime import datetime
# import plotly.express as px

import pandas as pd
import plotly.graph_objects as go

from portfoliohut.models import HistoricalEquity


def combine_data(list_series, friends_list, user_returns, index_returns):
    """
    Converts a list of dataframe into a formatted data frame for multi_plot to
    plot the returns data. Use the date time field as the index.
    """
    new_series_list = []
    for friends_returns, friends_name in zip(list_series, friends_list):
        new_df = friends_returns
        new_df = new_df.rename(friends_name)
        new_series_list.append(new_df)

    merged_df = pd.concat(new_series_list, axis=1)
    merged_df.insert(loc=0, column="My Returns", value=user_returns)
    merged_df.insert(loc=1, column="S&P 500", value=index_returns)
    return merged_df


def multi_plot(df, addAll=True):
    fig = go.Figure()

    for column in df.columns.to_list():
        fig.add_trace(go.Scatter(x=df.index, y=df[column], name=column))

    button_all = dict(
        label="All",
        method="update",
        args=[
            {"visible": df.columns.isin(df.columns), "title": "All", "showlegend": True}
        ],
    )

    def create_layout_button(column):
        return dict(
            label=column,
            method="update",
            args=[
                {
                    "visible": df.columns.isin([column, "My Returns", "Index"]),
                    "title": column,
                    "showlegend": True,
                }
            ],
        )

    fig.update_layout(
        updatemenus=[
            go.layout.Updatemenu(
                active=0,
                buttons=([button_all] * addAll)
                + list(df.columns.map(lambda column: create_layout_button(column))),
            )
        ]
    )

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
    graph = fig.to_html(full_html=False, default_width="90%", default_height="30%")
    return graph


def combine_index_user(user_returns, index_returns):
    user_returns = user_returns.rename("My Returns")
    index_returns = index_returns.rename("S&P 500")
    merged_df = pd.concat([user_returns, index_returns], axis=1)
    return merged_df.dropna()


def _get_sp_index(start_date=None):
    if start_date is not None:
        dates, closes = zip(
            *HistoricalEquity.objects.get_ticker("SPY")
            .filter(date__gte=start_date)
            .values_list("date", "close")
        )

    else:
        dates, closes = zip(
            *HistoricalEquity.objects.get_ticker("SPY").values_list("date", "close")
        )

    close_series = pd.Series(closes, index=dates).sort_index().astype(float)
    running_returns = close_series.dropna().pct_change()
    cumulative_series = (((1 + running_returns).cumprod()) - 1) * 100
    return cumulative_series
