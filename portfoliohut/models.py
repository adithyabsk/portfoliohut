import django_tables2 as tables
from django.contrib.auth.models import User
from django.db import models

STOCK_ACTIONS = (
    ("buy", "BUY"),
    ("sell", "SELL"),
)

CASH_BALANCE_ACTIONS = (("withdraw", "WITHDRAW"), ("deposit", "DEPOSIT"))


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT)
    bio = models.CharField(max_length=240, default="Hello! I'm new to Portfolio Hut.")

    friends = models.ManyToManyField("Profile", blank=True, related_name="friends_list")
    friend_requests = models.ManyToManyField(
        "Profile", blank=True, related_name="friend_requests_list"
    )

    def __str__(self):
        return f"user={self.user.get_full_name()}"


class CashBalance(models.Model):
    action = models.CharField(max_length=8, choices=CASH_BALANCE_ACTIONS)
    date_time = models.DateTimeField()
    profile = models.ForeignKey(Profile, on_delete=models.PROTECT)
    value = models.DecimalField(max_digits=100, decimal_places=2)

    def __str__(self):
        return (
            f"profile={self.profile.user.get_full_name()}, value={self.value}, "
            f"date_time={self.date_time}"
        )


class Stock(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.PROTECT)
    action = models.CharField(max_length=4, choices=STOCK_ACTIONS)
    ticker = models.CharField(max_length=20)  # must validate
    date_time = models.DateTimeField()
    price = models.DecimalField(max_digits=100, decimal_places=2)
    quantity = models.IntegerField()

    def __str__(self):
        return (
            f"ticker={self.ticker}, profile={self.profile.user.get_full_name()}, "
            f"date_time={self.date_time}"
        )


class StockTable(tables.Table):
    """
    This class is a helper class used by django_tables2. The library can
    convert a DB table to a HTML table based on the input model. This
    Columns can be customized with respect to user requirements. i.e no ID
    displayed in this table.
    Has in built pagination feature as well.
    """

    class Meta:
        model = Stock
        sequence = (
            "action",
            "ticker",
            "price",
            "quantity",
            "date_time",
        )
        exclude = (
            "profile",
            "id",
        )
        attrs = {"width": "160%"}
