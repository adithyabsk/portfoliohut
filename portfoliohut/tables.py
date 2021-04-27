import django_tables2 as tables
from django_tables2 import Column
from django_tables2.utils import A

from portfoliohut.models import PortfolioItem


class PortfolioItemTable(tables.Table):
    class Meta:
        model = PortfolioItem
        exclude = ("id", "profile")

    total_value = Column(
        accessor=A("total_value"),
    )
