from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now
from datetime import timedelta
import random
from decimal import Decimal  

def generate_unique_account_number():
    while True:
        account_number = str(random.randint(1000000000, 9999999999))  
        if not UserProfile.objects.filter(unique_account_number=account_number).exists():
            return account_number

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    investment_profit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    apexfin_coins = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    last_transaction_time = models.DateTimeField(null=True, blank=True)
    transaction_count = models.IntegerField(default=0)
    unique_account_number = models.CharField(max_length=10, unique=True, blank=True)
    is_activated = models.BooleanField(default=False)  
    cooldown_start = models.DateTimeField(null=True, blank=True)  

    def is_in_cooldown(self):
        if self.cooldown_start:
            return now() < (self.cooldown_start + timedelta(hours=36))
        return False

    def generate_unique_account_number(self):
        return generate_unique_account_number()

    def update_investment_profit(self):
        self.investment_profit = calculate_investment_profit(self.user)
        self.save()

    def save(self, *args, **kwargs):
        if not self.unique_account_number:
            self.unique_account_number = self.generate_unique_account_number()
        super().save(*args, **kwargs)

def calculate_investment_profit(user):
    """Calculates 5% profit on credited transactions in the last 90 days."""
    three_months_ago = now() - timedelta(days=90)
    transactions = Transaction.objects.filter(
        user=user, transaction_type="credit", timestamp__gte=three_months_ago
    )
    total_credited = sum(t.amount for t in transactions)
    return total_credited * Decimal("0.05")  # 5% profit

class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ("credit", "Credit"),
        ("debit", "Debit"),
        ("withdrawal", "Withdrawal"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_transactions")
    recipient = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="received_transactions")
    recipient_name = models.CharField(max_length=255, blank=True)
    recipient_account = models.CharField(max_length=10, blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    narration = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=now)

    def save(self, *args, **kwargs):
        profile = self.user.userprofile

        if self.transaction_type == "debit":
            if profile.transaction_count >= 3 and not profile.is_activated:
                if profile.last_transaction_time and (now() - profile.last_transaction_time < timedelta(hours=36)):
                    raise ValueError("Transaction limit exceeded. Try again in 36 hours.")
                else:
                    activation_fee = profile.balance * Decimal("0.01")
                    if profile.balance < activation_fee:
                        raise ValueError("Insufficient balance for activation fee.")
                    profile.balance -= activation_fee
                    profile.is_activated = True
                    profile.transaction_count = 0

            profile.transaction_count += 1
            profile.last_transaction_time = now()

        if self.transaction_type == "credit":
            profile.transaction_count = 0
            profile.update_investment_profit()

        if self.transaction_type == "withdrawal":
            gas_fee = self.amount * Decimal("0.03")
            if profile.balance < gas_fee:
                raise ValueError("Insufficient balance for gas fee.")
            profile.balance -= gas_fee

        profile.save()
        super().save(*args, **kwargs)
