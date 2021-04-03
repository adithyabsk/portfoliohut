from django.db import models
from django.contrib.auth.models import User

STOCK_ACTIONS = (
    ("buy", "BUY"),
    ("sell", "SELL"),
)

CASH_BALANCE_ACTIONS = (
    ("withdraw", "WITHDRAW"),
    ("deposit", "DEPOSIT")
)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT)
    bio = models.CharField(max_length=240)
    friends = models.ManyToManyField("Profile", blank=True, related_name='friends_list')
    friend_requests = models.ManyToManyField("Profile", blank=True, related_name='friend_requests_list')

    def __str__(self):
        return "Investor: " + self.user.get_full_name()


class CashBalance(models.Model):
    action = models.CharField(max_length=8, choices=CASH_BALANCE_ACTIONS)
    date_time = models.DateTimeField()
    profile = models.ForeignKey(Profile, on_delete=models.PROTECT)
    value = models.DecimalField(max_digits=100, decimal_places=2)

    def __str__(self):
        return "Profile: " + self.profile.user.get_full_name() + \
               "\nValue: " + self.value


class Stock(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.PROTECT)
    action = models.CharField(max_length=4, choices=STOCK_ACTIONS)
    ticker = models.CharField(max_length=20)  # must validate
    date_time = models.DateTimeField()
    price = models.DecimalField(max_digits=100, decimal_places=2)
    quantity = models.IntegerField()

    def __str__(self):
        return "Profile: " + self.profile.user.get_full_name() + \
               "\nAction: " + self.action + \
               "\nTicker: " + self.ticker + \
               "\nDate and Time: " + self.date_time + \
               "\nPrice: " + self.price + \
               "\nQuantity: " + self.quantity
