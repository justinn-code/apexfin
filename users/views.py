from django.utils import timezone
import os
from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.timezone import now, timedelta
from django.db import transaction
from decimal import Decimal
from .models import UserProfile, Transaction
from .forms import SendFundsForm, ReceiveFundsForm, ConvertToFiatForm
from django.contrib.auth.models import User
from django.db.models import Q
from .utils import verify_usdt_payment
import requests
from datetime import datetime, timedelta
import logging
from django.http import JsonResponse
from .models import CustomUser, UserProfile
from .forms import SignUpForm 
from django.views.decorators.csrf import csrf_exempt, csrf_protect  # ✅ Import both
from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from .models import UserLocation
from .utils import get_client_ip

logger = logging.getLogger(__name__)

# -------------------- Homepage View --------------------
def homepage(request):
    return render(request, 'homepage.html')

# -------------------- Signup View --------------------
def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            # ✅ Auto-create UserProfile after signup
            UserProfile.objects.create(user=user)  
            login(request, user)
            return redirect("/users/dashboard/")
    else:
        form = SignUpForm()
    return render(request, "users/signup.html", {"form": form})

# -------------------- Login View --------------------
def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, 'Login successful!')
            return redirect('users:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    else:
        form = AuthenticationForm()
    return render(request, 'users/login.html', {'form': form})

# -------------------- Logout View --------------------
def logout_view(request):
    logout(request)
    messages.success(request, 'Logged out successfully.')
    return redirect('users:homepage')

#---------------------Dashboard View-------------------
@login_required
def dashboard(request):
    # ✅ Optional: IPStack Location Tracking
    ipstack_key = getattr(settings, 'IPSTACK_API_KEY', None)
    if ipstack_key:
        try:
            ip = get_client_ip(request)
            url = f"http://api.ipstack.com/{ip}?access_key={ipstack_key}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                location_data = response.json()
                UserLocation.objects.create(
                    user=request.user,
                    ip_address=ip,
                    location=location_data.get('city', 'Unknown')
                )
        except Exception as e:
            print("IPStack location fetch failed:", str(e))

    # 🧾 Get transactions and profile
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    transactions = Transaction.objects.filter(
        Q(sender_account=profile.unique_account_number) |
        Q(recipient_account=profile.unique_account_number)
    ).order_by('-timestamp')

    unique_transactions = []
    seen_transactions = set()

    for transaction in transactions:
        transaction_identifier = f"{transaction.sender_account}-{transaction.recipient_account}-{transaction.timestamp}"

        if transaction_identifier not in seen_transactions:
            seen_transactions.add(transaction_identifier)

            if transaction.sender_account == profile.unique_account_number:
                direction = "Sent"
                try:
                    counterparty = UserProfile.objects.get(unique_account_number=transaction.recipient_account)
                    counterparty_name = counterparty.user.get_full_name() or counterparty.user.username
                except UserProfile.DoesNotExist:
                    counterparty_name = "Unknown"
                counterparty_account = transaction.recipient_account
            else:
                direction = "Received"
                try:
                    counterparty = UserProfile.objects.get(unique_account_number=transaction.sender_account)
                    counterparty_name = counterparty.user.get_full_name() or counterparty.user.username
                except UserProfile.DoesNotExist:
                    counterparty_name = "Unknown"
                counterparty_account = transaction.sender_account

            unique_transactions.append({
                'direction': direction,
                'amount': transaction.amount,
                'timestamp': transaction.timestamp,
                'narration': transaction.narration,
                'status': transaction.status,
                'counterparty_name': counterparty_name,
                'counterparty_account': counterparty_account,
            })

    context = {
        'profile': profile,
        'account_number': profile.unique_account_number,
        'balance': round(profile.balance, 2),
        'investment_profit': profile.investment_profit,
        'transactions': unique_transactions,
    }

    return render(request, 'users/dashboard.html', context)
# -------------------- Fund Account --------------------
@login_required
def fund_account(request):
    if request.method == 'POST':
        profile = UserProfile.objects.get(user=request.user)
        profile.balance += Decimal("1000.00")
        profile.save()
        messages.success(request, "Your account has been funded successfully!")
        return redirect('users:dashboard')
    return render(request, 'users/fund_account.html')

# -------------------- Activate ApexFin Coin --------------------
@login_required
def activate_profit_investment(request):
    user_profile = request.user.userprofile
    activation_fee = user_profile.balance * Decimal("0.01")  # 1% of balance

    if request.method == "POST":
        transaction_id = request.POST.get("transaction_id")

        if not transaction_id:
            messages.error(request, "Please enter your USDT transaction ID.")
        else:
            # Assume check_usdt_payment validates the transaction correctly
            transaction_verified = check_usdt_payment(request.user, activation_fee, transaction_id)

            if transaction_verified:
                user_profile.is_activated = True
                user_profile.cooldown_start = None  # Clear cooldown after activation
                user_profile.save()

                messages.success(request, "ApexFin Coin investment profit activated! Convert profit to fiat to resume transactions.")
                return redirect('convert_to_fiat')
            else:
                messages.error(request, "Payment verification failed. Ensure the correct amount was sent.")

    return render(request, "users/activate_profit_investment.html", {
        "activation_fee": activation_fee,
        "wallet_address": settings.USDT_WALLET_ADDRESS,
    })


# -------------------- Send Funds --------------------
@login_required
def send_funds(request):
    sender = request.user
    sender_profile = get_object_or_404(UserProfile, user=sender)

    # Check if the user has completed 3 debit transactions
    if sender_profile.debit_transaction_count >= 3:
        if not sender_profile.cooldown_start:
            sender_profile.cooldown_start = timezone.now()
            sender_profile.save()

        cooldown_end_time = sender_profile.cooldown_start + timedelta(hours=36)
        cooldown_remaining_seconds = (cooldown_end_time - timezone.now()).total_seconds()

        if cooldown_remaining_seconds > 0:
            return render(request, 'users/send_funds.html', {
                'cooldown_active': True,
                'cooldown_remaining': round(cooldown_remaining_seconds),
            })
        else:
            if not sender_profile.is_activated:
                return render(request, 'users/send_funds.html', {
                    'requires_activation': True,
                })

    # Handle fund transfer after checking cooldown/activation
    if request.method == "POST":
        recipient_account = request.POST.get("recipient_account")
        amount = request.POST.get("amount")
        narration = request.POST.get("narration", "")

        try:
            amount = Decimal(amount)
            if amount <= 0:
                return JsonResponse({"success": False, "error": "Invalid amount"}, status=400)
        except ValueError:
            return JsonResponse({"success": False, "error": "Amount must be a number"}, status=400)

        if sender_profile.balance < amount:
            return JsonResponse({"success": False, "error": "Insufficient funds"}, status=400)

        # Ensure recipient exists
        recipient_profile = UserProfile.objects.filter(unique_account_number=recipient_account).first()
        if not recipient_profile:
            return JsonResponse({"success": False, "error": "Recipient not found"}, status=404)

        try:
            # Process transaction inside atomic block
            with transaction.atomic():
                sender_profile.balance -= amount
                recipient_profile.balance += amount
                sender_profile.debit_transaction_count += 1
                sender_profile.save()
                recipient_profile.save()

                # Sender's transaction record (Debited)
                Transaction.objects.create(
                    user=sender,
                    sender_name=sender.get_full_name(),
                    sender_account=sender_profile.unique_account_number,
                    recipient_name=recipient_profile.user.get_full_name(),
                    recipient_account=recipient_profile.unique_account_number,
                    amount=amount,
                    narration=narration,
                    timestamp=timezone.now(),
                    transaction_type="debit",
                    status="completed",
                )

                # Recipient's transaction record (Credited)
                Transaction.objects.create(
                    user=recipient_profile.user,
                    sender_name=sender.get_full_name(),
                    sender_account=sender_profile.unique_account_number,
                    recipient_name=recipient_profile.user.get_full_name(),
                    recipient_account=recipient_profile.unique_account_number,
                    amount=amount,
                    narration=narration,
                    timestamp=timezone.now(),
                    transaction_type="credit",
                    status="completed",
                )

                # If 3 debit transactions are completed, start cooldown
                if sender_profile.debit_transaction_count >= 3:
                    sender_profile.cooldown_start = timezone.now()
                    sender_profile.save()

                return JsonResponse({"success": True, "message": "Transaction successful!"}, status=200)

        except Exception as e:
            return JsonResponse({"success": False, "error": f"Error processing transaction: {str(e)}"}, status=500)

    return render(request, 'users/send_funds.html', {
        'cooldown_active': False,
        'cooldown_remaining': None,
        'activation_required': False,
    })


#----------------------Recipiet Name---------------------
@login_required
def get_recipient_name(request):
    account_number = request.GET.get("account_number")

    if not account_number:
        return JsonResponse({"success": False, "error": "No account number provided"})

    try:
        user_profile = UserProfile.objects.get(unique_account_number=account_number)
        
        # Use full name or fallback to username
        recipient_name = user_profile.user.get_full_name().strip()
        if not recipient_name:
            recipient_name = user_profile.user.username  # Fallback to username

        return JsonResponse({"success": True, "recipient_name": recipient_name})

    except UserProfile.DoesNotExist:
        return JsonResponse({"success": False, "error": "Account not found"})

# -------------------- Receive Funds --------------------
@login_required
def receive_funds(request):
    profile = UserProfile.objects.get(user=request.user)

    if request.method == 'POST':
        form = ReceiveFundsForm(request.POST)
        if form.is_valid():
            amount = form.cleaned_data['amount']
            sender_account = form.cleaned_data['sender_account']

            try:
                sender_profile = UserProfile.objects.get(unique_account_number=sender_account)

                if sender_profile.balance < amount:
                    messages.error(request, "Sender has insufficient balance.")
                    return redirect('users:receive_funds')

                # Deduct from sender's balance
                sender_profile.balance -= amount
                sender_profile.save()

                # Add to recipient's balance
                profile.balance += amount
                profile.save()

                # Log the transaction with sender and recipient details
                Transaction.objects.create(
                    user=request.user,
                    sender_name=sender_profile.user.username,
                    sender_account=sender_profile.unique_account_number,
                    recipient_name=request.user.username,
                    recipient_account=profile.unique_account_number,
                    amount=amount,
                    transaction_type='credit',
                    narration=f"Received from {sender_profile.user.username}"
                )

                messages.success(request, "Funds received successfully!")
                return redirect('users:dashboard')
            except UserProfile.DoesNotExist:
                messages.error(request, "Invalid sender account number.")
    else:
        form = ReceiveFundsForm()

    context = {
        'form': form,
        'account_number': profile.unique_account_number
    }

    return render(request, 'users/receive_funds.html', context)

# -------------------- Transaction History --------------------
@login_required
def transaction_history(request):
    user = request.user
    transactions = Transaction.objects.filter(user=user).order_by('-timestamp')

    transaction_history = []
    for txn in transactions:
        label = txn.transaction_type  # 'Sent' or 'Received'

        if label == "Sent":
            counterparty = txn.recipient_name or txn.recipient_account
        else:
            counterparty = txn.sender_name or txn.sender_account

        transaction_history.append({
            'label': label,
            'counterparty': counterparty,
            'amount': txn.amount,
            'narration': txn.narration,
            'timestamp': txn.timestamp,
            'status': txn.status
        })

    return render(request, 'users/transaction_history.html', {
        'transaction_history': transaction_history
    })

#---------------------Verification USDT payment------------
def check_usdt_payment(user, gas_fee, transaction_id):
    api_url = settings.TRONSCAN_API_URL
    api_key = settings.TRONSCAN_API_KEY

    try:
        response = requests.get(
            f"{api_url}?hash={transaction_id}&apikey={api_key}",
            timeout=10  # Timeout to avoid long waits
        )
        response.raise_for_status()

        transaction_data = response.json()

        # Debugging: Print the response to verify
        print("TronScan Response:", transaction_data)

        # Assuming 'value' holds the amount sent in USDT
        if transaction_data.get("confirmed") and transaction_data.get("value") >= float(gas_fee):
            return True

    except requests.exceptions.RequestException as e:
        print("Error connecting to TronScan API:", e)

    return False

# -------------------- Convert to Fiat --------------------
@login_required
def convert_to_fiat(request):
    user_profile = request.user.userprofile
    gas_fee = user_profile.investment_profit * Decimal("0.03")  # 3% of investment profit

    if request.method == "POST":
        transaction_id = request.POST.get("transaction_id")

        if not transaction_id:
            messages.error(request, "Please enter your USDT transaction ID.")
        else:
            transaction_verified = check_usdt_payment(request.user, gas_fee, transaction_id)

            if transaction_verified:
                user_profile.is_converted = True
                user_profile.save()
                messages.success(request, "Conversion to fiat successful! You can now resume transactions.")
                return redirect('dashboard')
            else:
                messages.error(request, "Payment verification failed. Please try again.")

    return render(request, "users/convert_to_fiat.html", {
        "gas_fee": gas_fee,
        "wallet_address": settings.USDT_WALLET_ADDRESS,
    })

# -------------------- All Users View --------------------
@login_required
def all_users(request):
    users = User.objects.all()  # Adjusted to use Django's default User model
    return render(request, 'users/all_users.html', {'users': users})

# -------------------- Cooldown Message --------------------
@login_required
def cooldown_message(request):
    profile = UserProfile.objects.get(user=request.user)
    cooldown_remaining = (profile.cooldown_start + timedelta(hours=36) - now()).total_seconds() // 3600 if profile.cooldown_start else 0
    return render(request, 'users/cooldown_message.html', {'cooldown_remaining': cooldown_remaining})
#---------------------Tracker_ip-----------------------------
@login_required
def track_user_location(request):
    # Get the user's IP address
    ip_address = request.META.get('REMOTE_ADDR')
    
    # Use ipstack API to get the location information
    api_url = f"http://api.ipstack.com/{ip_address}?access_key={settings.IPSTACK_API_KEY}"
    response = requests.get(api_url)
    
    if response.status_code == 200:
        location_data = response.json()
        country = location_data.get('country_name')
        city = location_data.get('city')
        region = location_data.get('region_name')

        # Store the location info in the database
        UserLocation.objects.create(
            ip_address=ip_address,
            country=country,
            city=city,
            region=region,
            timestamp=timezone.now(),
        )

def dashboard(request):
    # Track user location
    track_user_location(request)

    # Get the most recent location for the user
    user_location = UserLocation.objects.filter(ip_address=request.META.get('REMOTE_ADDR')).order_by('-timestamp').first()

    # Pass the location data to the template
    context = {
        'user': request.user,
        'account_number': '12345',  # Example data
        'balance': 1000,  # Example data
        'investment_profit': 200,  # Example data
        'in_cooldown': False,  # Example data
        'cooldown_end': '2025-04-10 10:00:00',  # Example data
        'user_profile': request.user.profile,  # Example user profile data
        'activation_fee': 10,  # Example data
        'conversion_fee': 15,  # Example data
        'requires_conversion': True,  # Example data
        'user_location': user_location,  # Pass the location to template
    }

    return render(request, 'dashboard.html', context)