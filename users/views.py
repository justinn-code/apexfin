from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from .models import UserProfile, Transaction, AddFundRequest  # Your models
from .forms import SendFundsForm, ReceiveFundsForm, ConvertToFiatForm, AddFundForm
from django.contrib.admin.views.decorators import staff_member_required  # For admin views
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta
import requests  # For external API calls like verifying payments
import logging
from django.db.models import Q
from .forms import SignUpForm  # Import custom form
from decimal import Decimal
from django.conf import settings
import os
from django.http import HttpResponse

logger = logging.getLogger(__name__)

# -------------------- Homepage View --------------------
def homepage(request):
    return render(request, 'homepage.html')

# -------------------- Admin: Review Gift Card Requests --------------------
@staff_member_required
def review_add_fund_requests(request):
    pending_requests = AddFundRequest.objects.filter(status='pending', payment_method='gift_card')

    if request.method == 'POST':
        request_id = request.POST.get('request_id')
        action = request.POST.get('action')
        admin_note = request.POST.get('admin_note', '')

        # Validate inputs to ensure they are not empty
        if not request_id:
            messages.error(request, "Request ID is required.")
            return redirect('review_add_fund_requests')

        if not action:
            messages.error(request, "Action (approve/reject) is required.")
            return redirect('review_add_fund_requests')

        try:
            add_request = AddFundRequest.objects.get(id=request_id)

            # Start atomic block for transaction integrity
            with transaction.atomic():
                if action == 'approve':
                    add_request.status = 'approved'
                    add_request.admin_note = admin_note
                    add_request.save()

                    # Add funds to the user's profile
                    profile = UserProfile.objects.get(user=add_request.user)
                    profile.balance += add_request.amount
                    profile.save()

                    messages.success(request, f"Request {request_id} approved and funded.")
                
                elif action == 'reject':
                    add_request.status = 'rejected'
                    add_request.admin_note = admin_note
                    add_request.save()

                    messages.warning(request, f"Request {request_id} rejected.")

                else:
                    messages.error(request, "Invalid action.")
                    return redirect('review_add_fund_requests')

        except AddFundRequest.DoesNotExist:
            messages.error(request, "Request not found.")
        except UserProfile.DoesNotExist:
            messages.error(request, "User profile not found.")
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {str(e)}")

        return redirect('review_add_fund_requests')

    return render(request, 'admin/review_add_fund_requests.html', {
        'pending_requests': pending_requests,
    })

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
@login_required
def activate_profit_investment(request):
    user_profile = request.user.userprofile
    activation_fee = user_profile.balance * Decimal("0.01")  # 1% of balance

    # Format activation fee with commas
    formatted_activation_fee = "{:,.2f}".format(activation_fee)

    if request.method == "POST":
        payment_method = request.POST.get("payment_method")
        
        if payment_method == "usdt":
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
                    messages.error(request, "USDT payment verification failed. Ensure the correct amount was sent.")

        elif payment_method == "gift_card":
            gift_card_code = request.POST.get("gift_card_code")

            if not gift_card_code:
                messages.error(request, "Please enter your gift card code.")
            else:
                # Assume check_gift_card_payment validates the gift card code correctly
                gift_card_verified = check_gift_card_payment(request.user, activation_fee, gift_card_code)

                if gift_card_verified:
                    user_profile.is_activated = True
                    user_profile.cooldown_start = None  # Clear cooldown after activation
                    user_profile.save()

                    messages.success(request, "ApexFin Coin investment profit activated! Convert profit to fiat to resume transactions.")
                    return redirect('convert_to_fiat')
                else:
                    messages.error(request, "Gift card verification failed. Ensure the correct value is entered.")

    # USDT wallet address
    wallet_address = settings.USDT_WALLET_ADDRESS

    return render(request, "users/activate_profit_investment.html", {
        "formatted_activation_fee": formatted_activation_fee,
        "wallet_address": wallet_address,
    })

# -------------------- Addd Funds --------------------
@login_required
def add_funds(request):
    if request.method == 'POST':
        form = AddFundForm(request.POST, request.FILES)
        if form.is_valid():
            add_fund = form.save(commit=False)
            add_fund.user = request.user
            add_fund.status = 'pending'
            add_fund.save()

            # Message for user
            if add_fund.payment_method == 'gift_card':
                messages.info(request, "Gift card submitted. Await admin approval.")
            elif add_fund.payment_method == 'bank_transfer':
                messages.info(request, "Bank transfer details submitted. Await admin review.")
            elif add_fund.payment_method == 'crypto':
                messages.info(request, "Awaiting automatic verification of your crypto transfer...")

            # Redirect after post
            return redirect('add_funds')
    else:
        form = AddFundForm()
    return render(request, 'add_funds.html', {'form': form})


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
                    transaction_type="Sent",
                    status="completed",
                    balance_after=sender_profile.balance,
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
                    transaction_type="Received",
                    status="completed",
                    balance_after=recipient_profile.balance,
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

    history = []
    for txn in transactions:
        if txn.user == user:  # Check if the logged-in user is involved in the transaction
            if txn.transaction_type == 'credit':  # If it's a credit transaction (received)
                label = 'Received'
                counterparty = f"{txn.sender_name} ({txn.sender_account})"
            else:  # If it's a debit or withdrawal (sent)
                label = 'Sent'
                counterparty = f"{txn.recipient_name} ({txn.recipient_account})"

            history.append({
                'timestamp': txn.timestamp,
                'label': label,
                'amount': txn.amount,
                'counterparty': counterparty,
                'narration': txn.narration,
                'status': 'Success' if txn.status == 'completed' else 'Failed',
                'balance_after': txn.balance_after,
            })

    return render(request, 'users/transaction_history.html', {'transaction_history': history})

#---------------------Activatin Profit Investment----------
@login_required
def activate_profit_investment(request):
    user = request.user  # Get the logged-in user
    try:
        # Access the profile related to the user
        user_profile = user.profile
    except UserProfile.DoesNotExist:
        # If the user doesn't have a profile, create it
        user_profile = UserProfile.objects.create(user=user)
        print(f"Created profile for {user.username}")  # Debugging line (optional)

    # Calculate the activation fee (1% of the user's balance)
    activation_fee = user_profile.balance * 0.01

    # Check if the user has activated the profit investment
    if user_profile.is_activated:
        return HttpResponse("Your account is already activated.", status=200)

    # Add your activation logic (e.g., marking the user as activated)
    # You can also implement logic to handle cooldown periods
    user_profile.is_activated = True
    user_profile.save()

    # Return a response to confirm the activation
    return render(request, 'activate_profit_investment.html', {
        'user_profile': user_profile,
        'activation_fee': activation_fee,
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

#---------------------Verification Gift Card payment------------
def check_gift_card_payment(user, required_amount, gift_card_code):
    try:
        # Example: Check if the gift card code exists in the database and its value
        gift_card = GiftCard.objects.get(code=gift_card_code)

        # Check if the gift card value is sufficient
        if gift_card.value >= required_amount:
            return True

    except GiftCard.DoesNotExist:
        print("Gift card not found.")
    
    return False

# -------------------- Convert to Fiat --------------------
@login_required
def convert_to_fiat(request):
    user_profile = request.user.userprofile
    gas_fee = user_profile.investment_profit * Decimal("0.03")  # 3% of investment profit

    if request.method == "POST":
        payment_method = request.POST.get("payment_method")
        
        # If Payment Method is USDT
        if payment_method == "usdt":
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

        # If Payment Method is Gift Card
        elif payment_method == "gift_card":
            gift_card_type = request.POST.get("gift_card_type")
            gift_card_code = request.POST.get("gift_card_code")
            gift_card_reference = request.POST.get("gift_card_reference", "")

            if not gift_card_type or not gift_card_code:
                messages.error(request, "Please enter the gift card type and code.")
            else:
                # Validate the gift card code (this would depend on your validation method)
                gift_card_valid = validate_gift_card(gift_card_type, gift_card_code)

                if gift_card_valid:
                    # Assuming the gift card amount matches the gas fee (this logic can be expanded)
                    user_profile.is_converted = True
                    user_profile.save()
                    messages.success(request, f"Gift Card payment successful! You can now resume transactions.")
                    return redirect('dashboard')
                else:
                    messages.error(request, "Gift Card verification failed. Please try again.")

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
