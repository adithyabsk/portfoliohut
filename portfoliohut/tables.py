import itertools
import math

from django.shortcuts import reverse
from django.utils.html import mark_safe
from django_tables2 import Column, tables
from django_tables2.utils import A

from portfoliohut.models import PortfolioItem, Profile, Transaction


class PortfolioItemTable(tables.Table):
    total_value = Column(accessor=A("total_value"))
    # action = Column(accessor=A("viewable_type"))

    class Meta:
        model = PortfolioItem
        exclude = ("id", "profile", "created")
        sequence = ("type", "ticker", "quantity", "price", "total_value")
        orderable = False

    def render_total_value(self, value):
        return "${:,}".format(value)

    def render_price(self, value):
        return "${:,}".format(value)


class ReturnsTable(tables.Table):
    rank = Column(empty_values=())
    percent_returns = Column(accessor=A("get_most_recent_return"))

    class Meta:
        model = Profile
        exclude = ("id", "bio", "profile_type")
        sequence = ("rank", "user", "percent_returns")
        row_attrs = {"data-username": lambda record: record.user.username}
        orderable = False

    # Add row counter to django_tables2
    # https://stackoverflow.com/questions/37694971/how-to-add-counter-column-in-django-tables2
    def render_rank(self):
        self.row_counter = getattr(
            self, "row_counter", itertools.count(self.page.start_index())
        )
        return next(self.row_counter)

    def render_percent_returns(self, value):
        if not math.isnan(value):
            return "{:0.2f}%".format(value)
        return "No Return %"

    # Add clickable link to user's profile page
    # https://stackoverflow.com/questions/22941424/django-tables2-create-extra-column-with-links
    def render_user(self, record):
        return mark_safe(
            "<a href={function}>{username}<a>".format(
                function=reverse("profile", args=[record.user.username]),
                username=record.user.username,
            )
        )


class TransactionTable(tables.Table):
    """
    This class is a helper class used by django_tables2. The library can
    convert a DB table to a HTML table based on the input model. This
    Columns can be customized with respect to user requirements. i.e no ID
    displayed in this table.
    Has in built pagination feature as well.
    """

    action = Column(accessor="quantity_annotator", verbose_name="Action")
    # viewable_quantity = Column(accessor="viewable_quantity", verbose_name="Quantity")

    class Meta:
        model = Transaction
        sequence = ("action", "ticker", "date_time", "quantity", "price")
        exclude = ("type", "profile", "id", "time")
        attrs = {"width": "100%"}
        orderable = False

    def render_total_value(self, value):
        return "${:,}".format(value)

    def render_price(self, value):
        return "${:,}".format(value)
