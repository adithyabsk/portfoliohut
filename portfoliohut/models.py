from django.db import models
from django.contrib.auth.models import User

ACTION_CHOICES = (
    ('buy','BUY'),
    ('sell', 'SELL'),
)

class Profile(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

	def __str__(self):
		return 'Investor: ' + self.user.get_full_name()

class CashBalance(models.Model):
	profile = models.ForeignKey(Profile, on_delete=models.PROTECT) 
	value = models.DecimalField(max_digits=100, decimal_places=2)

	def __str__(self):
		return 'Profile: ' + self.profile.user.get_full_name() + \
               '\nValue: ' + self.value 

class Stock(models.Model):
	profile = models.ForeignKey(Profile, on_delete=models.PROTECT) 
	action = models.CharField(max_length=4, choices=ACTION_CHOICES, default='buy')
	ticker = models.CharField(max_length=10) # must validate
	date_time = models.DateTimeField()
	price = models.DecimalField(max_digits=100, decimal_places=2)
	quantity = models.IntegerField(default=-1)

	def __str__(self):
		return 'Profile: ' + self.profile.user.get_full_name() + \
               '\nAction: ' + self.action + \
               '\nTicker: ' + self.ticker + \
               '\nDate and Time: ' + self.date_time + \
               '\nPrice: ' + self.price + \
               '\nQuantity: ' + self.quantity