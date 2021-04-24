import django_tables2 as tables
from django.db import models
from django.utils.translation import gettext_lazy as _


class FinancialItem(models.Model):
    class FinancialActionType(models.TextChoices):
        EQUITY = "EQ", _("Equity")
        EXTERNAL_CASH = "EC", _("External Cash")
        INTERNAL_CASH = "IC", _("Internal Cash")

    class Meta:
        abstract = True

    type = models.CharField(max_length=4, choices=FinancialActionType.choices)
    ticker = models.CharField(max_length=20, blank=True)
    date = models.DateField()

    def display_items(self):
        return [f"date={self.date}"]

    def __str__(self):
        return ", ".join(self.display_items())


CASH = (
    FinancialItem.FinancialActionType.EXTERNAL_CASH,
    FinancialItem.FinancialActionType.INTERNAL_CASH,
)


class Transaction(FinancialItem):
    """An individual transaction."""

    profile = models.ForeignKey("portfoliohut.Profile", on_delete=models.PROTECT)
    time = models.TimeField()
    quantity = models.IntegerField()  # positive for buy negative for sell
    price = models.DecimalField(
        max_digits=100, decimal_places=2
    )  # always greater than zero

    def display_items(self):
        items = super().display_items()
        items.append(f"profile={self.profile.user.get_full_name()}")
        if self.type == FinancialItem.FinancialActionType.EQUITY:
            items.extend([f"ticker={self.ticker}"])
        elif self.type in CASH:
            action = "deposit" if self.quantity > 0 else "withdrawal"
            items.append(f"{action}={self.price}")

        return items


class PortfolioItem(FinancialItem):
    """An item in a portfolio."""

    profile = models.ForeignKey("portfoliohut.Profile", on_delete=models.PROTECT)
    quantity = models.IntegerField()  # positive for buy negative for sell
    price = models.DecimalField(
        max_digits=100, decimal_places=2
    )  # always greater than zero
    cost_average = models.DecimalField(max_digits=100, decimal_places=2)

    def display_items(self):
        items = super().display_items()
        items.append(f"profile={self.profile.user.get_full_name()}")
        if self.type == FinancialItem.FinancialActionType.EQUITY:
            items.extend([f"ticker={self.ticker}"])
        elif self.type in CASH:
            action = "deposit" if self.quantity > 0 else "withdrawal"
            items.append(f"{action}={self.price}")

        return items


class HistoricalEquity(FinancialItem):
    """Hold the history of a particular equity over time."""

    open = models.DecimalField(max_digits=100, decimal_places=2)
    high = models.DecimalField(max_digits=100, decimal_places=2)
    low = models.DecimalField(max_digits=100, decimal_places=2)
    close = models.DecimalField(max_digits=100, decimal_places=2)
    volume = models.IntegerField()
    dividends = models.DecimalField(max_digits=100, decimal_places=2)
    stock_splits = models.IntegerField()

    def display_items(self):
        items = super().display_items()
        if self.type == FinancialItem.FinancialActionType.EQUITY:
            items.extend([f"ticker={self.ticker}"])


class EquityInfo(models.Model):
    ticker = models.CharField(max_length=20)
    logo_url = models.URLField()
    # Add other attributes from yf.Ticker().info as needed

    def __str__(self):
        return f"ticker={self.ticker}"


class PortfolioReturn(models.Model):
    """The rolling return on a particular day for a portfolio"""

    profile = models.ForeignKey("portfoliohut.Profile", on_delete=models.PROTECT)
    date_time = models.DateTimeField()
    floating_return = models.FloatField()

    def __str__(self):
        return f"profile={self.profile}, floating_return={self.floating_return:.2f}"


class TransactionTable(tables.Table):
    """
    This class is a helper class used by django_tables2. The library can
    convert a DB table to a HTML table based on the input model. This
    Columns can be customized with respect to user requirements. i.e no ID
    displayed in this table.
    Has in built pagination feature as well.
    """

    class Meta:
        model = Transaction
        sequence = (
            "type",
            "ticker",
            "price",
            "quantity",
            "date",
            "time",
        )
        exclude = (
            "profile",
            "id",
        )
        attrs = {"width": "160%"}
