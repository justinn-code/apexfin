from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.timezone import now
from datetime import timedelta
from decimal import Decimal
import random
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


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


# Custom User model
class CustomUser(AbstractUser):
    account_number = models.CharField(max_length=20, unique=True, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = generate_unique_account_number()
        super().save(*args, **kwargs)


# UserProfile for extra user info
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
        if self.cooldown_start:
            return now() < self.cooldown_start + timedelta(hours=36)
        return False

    def requires_activation(self):
        return self.transaction_count >= 3 and not self.is_activated

    def requires_conversion(self):
        return self.is_activated and not self.is_converted and self.investment_profit > 0

    def __str__(self):
        return f"{self.user.username}'s Profile"


# Signals to automatically create a UserProfile when a CustomUser is created
@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile instance for the newly created CustomUser."""
    if created:
        UserProfile.objects.create(user=instance)


# Signals to save the UserProfile after the CustomUser is saved
@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    """Save the UserProfile instance after the CustomUser is saved."""
    # Ensure the profile is created if it doesn't exist
    instance.profile.save()


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
    balance_after = models.DecimalField(default=0, max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        # Access the profile correctly
        profile, _ = UserProfile.objects.get_or_create(user=self.user)


        if self.transaction_type == "debit":
            if profile.requires_activation():
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
        if self.user == current_user:
            return 'Sent' if self.transaction_type == "debit" else 'Received'
        else:
            return 'Sent' if self.transaction_type == "credit" else 'Received'

    def get_counterparty_name(self, current_user):
        return self.recipient_name if self.user == current_user else self.sender_name

    def get_counterparty_account(self, current_user):
        return self.recipient_account if self.user == current_user else self.sender_account


# AddFundRequest Model
class AddFundRequest(models.Model):
    PAYMENT_METHODS = [
        ('gift_card', 'Gift Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('crypto', 'Crypto (USDT)'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    gift_card_code = models.CharField(max_length=255, blank=True, null=True)
    gift_card_image = models.ImageField(upload_to='gift_cards/', blank=True, null=True)
    bank_details = models.TextField(blank=True, null=True)
    crypto_wallet_address = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, default='pending')  # pending / approved / rejected
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)  # New field to mark verification status

    def __str__(self):
        return f"{self.user.username} - {self.payment_method.title()} - ${self.amount:,.2f}"
