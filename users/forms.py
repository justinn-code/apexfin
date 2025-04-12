from django import forms
from django.contrib.auth.forms import UserCreationForm
from decimal import Decimal
from .models import Transaction, CustomUser, AddFundRequest


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email Address")

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("Email is already in use.")
        return email


class SendFundsForm(forms.Form):
    recipient_account = forms.CharField(label="Recipient Account Number", max_length=20)
    amount = forms.DecimalField(label="Amount", min_value=1, decimal_places=2)
    narration = forms.CharField(label="Narration (Optional)", required=False, max_length=100)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= Decimal("0.00"):
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount


class AddFundForm(forms.ModelForm):
    class Meta:
        model = AddFundRequest
        fields = ['payment_method', 'amount', 'gift_card_code', 'gift_card_image', 'bank_details', 'crypto_wallet_address']


class ReceiveFundsForm(forms.Form):
    sender_account = forms.CharField(max_length=10, label="Sender Account Number")
    amount = forms.DecimalField(max_digits=15, decimal_places=2, label="Amount")

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount <= Decimal("0.00"):
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount


class ActivateProfitForm(forms.Form):
    confirm_activation = forms.BooleanField(
        label="I agree to pay a 1% activation fee to activate investment profit."
    )


class ConvertBalanceForm(forms.Form):
    confirm_conversion = forms.BooleanField(
        label="I agree to pay a 3% gas fee to convert my balance (ApexFin Coin) to fiat currency."
    )


class ConvertToFiatForm(forms.Form):
    amount = forms.DecimalField(
        label="Amount to Convert",
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0.01')
    )
