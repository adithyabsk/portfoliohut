from django.db import models
from django.contrib.auth.models import User

ACTION_CHOICES = (
    ('buy','BUY'),
    ('sell', 'SELL'),
)

class Profile(models.Model):
	user = models.OneToOne(User, on_delete=CASCADE, related_name='profile')

	def __str__(self):
		return 'Investor: ' + self.user.get_full_name()

class CashBalance(models.Model):
	profile = models.ForeignKey(Profile, on_delete=PROTECT) 
	value = DecimalField(decimal_places=2)

	def __str__(self):
		return 'Profile: ' + self.profile.user.get_full_name() + \
               '\nValue: ' + self.value 

class Stock(models.Model):
	profile = models.ForeignKey(Profile, on_delete=PROTECT) 
	action = models.CharField(max_length=4, choices=ACTION_CHOICES, default='buy')
	ticker = models.CharField(max_length=10) # must validate
	date = DateTimeField()
	buy_price = models.DecimalField(decimal_places=2)
	quantity = models.IntegerFiled(default=-1)

	def __str__(self):
		return 'Profile: ' + self.profile.user.get_full_name() + \
               '\nAction: ' + self.action + \
               '\nTicker: ' + self.ticker + \
               '\nTicker: ' + self.date + \
               '\nBuy price: ' + self.buy_price + \
               '\nQuantity: ' + self.quantity