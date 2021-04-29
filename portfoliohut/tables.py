import itertools

import django_tables2 as tables
from django.shortcuts import reverse
from django.utils.html import mark_safe
from django_tables2 import Column
from django_tables2.utils import A

from portfoliohut.models import PortfolioItem, Profile


class PortfolioItemTable(tables.Table):
    total_value = Column(
        accessor=A("total_value"),
    )
    action = Column(
        accessor=A("viewable_type"),
    )

    class Meta:
        model = PortfolioItem
        exclude = ("id", "profile", "type")
        sequence = ("action", "ticker", "created", "quantity", "price", "total_value")


class ReturnsTable(tables.Table):
    rank = tables.Column(empty_values=())
    percent_returns = Column(
        accessor=A("get_most_recent_return"),
    )

    class Meta:
        model = Profile
        exclude = ("id", "bio", "profile_type")
        sequence = ("rank", "user", "percent_returns")

    # Add row counter to django_tables2
    # https://stackoverflow.com/questions/37694971/how-to-add-counter-column-in-django-tables2
    def render_rank(self):
        self.row_counter = getattr(
            self, "row_counter", itertools.count(self.page.start_index())
        )
        return next(self.row_counter)

    def render_percent_returns(self, value):
        return "{:0.2f}".format(value)

    # Add clickable link to user's profile page
    # https://stackoverflow.com/questions/22941424/django-tables2-create-extra-column-with-links
    def render_user(self, record):
        return mark_safe(
            "<a href="
            + reverse("profile", args=[record.user.username])
            + ">"
            + record.user.username
            + "</a>"
        )
