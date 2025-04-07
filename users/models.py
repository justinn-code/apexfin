from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.timezone import now
from datetime import timedelta
from decimal import Decimal
import random
from django.conf import settings

# Function to generate a unique account number
def generate_unique_account_number():
    """Generate a unique 10-digit account number."""
    while True:
        account_number = str(random.randint(1000000000, 9999999999))
        if not UserProfile.objects.filter(unique_account_number=account_number).exists():
            return account_number

# Custom manager for the user
class CustomUserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(username, email, password, **extra_fields)

# Custom User model inheriting from AbstractUser
class CustomUser(AbstractUser):
    account_number = models.CharField(max_length=20, unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = generate_unique_account_number()
        super().save(*args, **kwargs)

# UserProfile model for storing extra user info
class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    investment_profit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    apexfin_coins = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal("0.00"))
    transaction_count = models.IntegerField(default=0)
    last_transaction_time = models.DateTimeField(null=True, blank=True)
    unique_account_number = models.CharField(max_length=10, unique=True, blank=True)
    is_activated = models.BooleanField(default=False)
    cooldown_start = models.DateTimeField(null=True, blank=True)
    is_converted = models.BooleanField(default=False)
    debit_transaction_count = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.unique_account_number:
            self.unique_account_number = generate_unique_account_number()
        super().save(*args, **kwargs)

    def is_in_cooldown(self):
        """Check if the account is in cooldown period."""
        if self.cooldown_start:
            return now() < self.cooldown_start + timedelta(hours=36)
        return False

    def requires_activation(self):
        """Check if activation is needed for this user profile."""
        return self.transaction_count >= 3 and not self.is_activated

    def requires_conversion(self):
        """Check if coin-to-fiat conversion is needed."""
        return self.is_activated and not self.is_converted and self.investment_profit > 0

    def __str__(self):
        return f"{self.user.username}'s Profile"

# Transaction model for logging user transactions
class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ("credit", "Credit"),
        ("debit", "Debit"),
        ("withdrawal", "Withdrawal"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sender_name = models.CharField(max_length=255, blank=True)
    sender_account = models.CharField(max_length=10, blank=True)
    recipient_name = models.CharField(max_length=255, blank=True)
    recipient_account = models.CharField(max_length=10, blank=True)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    narration = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=now)
    status = models.CharField(max_length=20, default='completed')

    def save(self, *args, **kwargs):
        profile = self.user.userprofile

        # Handling transaction logic
        if self.transaction_type == "debit":
            if profile.requires_activation() and profile.transaction_count >= 3:
                profile.cooldown_start = now()
                profile.save()
                raise ValueError("Transaction limit reached. Activation required after cooldown.")
            
            if profile.requires_conversion():
                raise ValueError("Convert ApexFin Coin to fiat (3% gas fee in USDT required).")

            if profile.balance < self.amount:
                raise ValueError("Insufficient balance for the transaction.")

            profile.balance -= self.amount
            profile.transaction_count += 1

        elif self.transaction_type == "credit":
            profile.balance += self.amount
            profile.transaction_count = 0

        elif self.transaction_type == "withdrawal":
            gas_fee = self.amount * Decimal("0.03")
            if profile.balance < (self.amount + gas_fee):
                raise ValueError("Insufficient balance for withdrawal and gas fee.")
            profile.balance -= (self.amount + gas_fee)

        profile.save()
        super().save(*args, **kwargs)

    def get_transaction_direction(self, current_user):
        """Determine whether the transaction is 'Sent' or 'Received'."""
        if self.user == current_user:
            if self.transaction_type == "debit":
                return 'Sent'  # Outgoing transaction (Sent)
            else:
                return 'Received'  # Incoming transaction (Received)
        else:
            if self.transaction_type == "credit":
                return 'Sent'  # Outgoing transaction from the other party (Sent)
            else:
                return 'Received'  # Incoming transaction to the current user (Received)

    def get_counterparty_name(self, current_user):
        """Get the counterparty's name."""
        if self.user == current_user:
            return self.recipient_name  # Name of the recipient if the user is the sender
        else:
            return self.sender_name  # Name of the sender if the user is the recipient

    def get_counterparty_account(self, current_user):
        """Get the counterparty's account number."""
        if self.user == current_user:
            return self.recipient_account  # Account number of the recipient if the user is the sender
        else:
            return self.sender_account  # Account number of the sender if the user is the recipient


class UserLocation(models.Model):
    ip_address = models.GenericIPAddressField()
    country = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    region = models.CharField(max_length=255)
    timestamp = models.DateTimeField()

    def __str__(self):
        return f"{self.city}, {self.country} - {self.timestamp}"