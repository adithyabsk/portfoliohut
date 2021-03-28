from django.db import models
from django.contrib.auth.models import User
from djmoney.models.fields import MoneyField

# Create your models here.
class Investor(models.Model):
	profile = models.OneToOne(User, on_delete=CASCADE, related_name='profile')

	def __str__(self):
		return 'Investor: ' + self.profile.get_full_name()

class Transactions(models.Model):
	investor = models.ForeignKey(Investor, on_delete=PROTECT) 
	ticker = models.CharField(max_length=10)
	buy_price = models.DecimalField(decimal_places=2)
	quantity = models.IntegerFiled(default=-1)

	def __str__(self):
		return 'Investor: ' + self.investor.profile.get_full_name() +  
               '\nTicker: ' + self.ticker +  
               '\nBuy price: ' + self.buy_price +  
               '\nQuantity: ' + self.quantity 