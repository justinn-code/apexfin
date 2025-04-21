from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from .models import UserProfile, Transaction, AddFundRequest, GiftCard, FiatConversionRequest  # Your models
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
from .utils import check_usdt_payment, check_gift_card_payment, save_uploaded_file # Ensure these are imported correctly
from django.core.files.storage import default_storage
from django.views.decorators.csrf import csrf_exempt  # only if needed
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.core.mail import send_mail

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
def add_funds_view(request):
    if request.method == 'POST':
        form = AddFundForm(request.POST, request.FILES)
        
        if form.is_valid():
            fund_request = form.save(commit=False)
            fund_request.user = request.user

            if fund_request.payment_method == 'gift_card':
                code = fund_request.gift_card_code
                if not code:
                    messages.error(request, "Please provide a valid gift card code.")
                    return redirect('add_funds')

                try:
                    gift_card = GiftCard.objects.get(code=code)
                    fund_request.amount = gift_card.value
                    fund_request.save()
                    messages.success(request, "Gift card submitted. Awaiting admin approval.")
                except GiftCard.DoesNotExist:
                    messages.error(request, "Invalid gift card code.")
                    return redirect('add_funds')

            elif fund_request.payment_method == 'crypto':
                if not fund_request.crypto_wallet_address:
                    messages.error(request, "Please provide your USDT wallet address.")
                    return redirect('add_funds')

                fund_request.save()
                messages.success(request, "Crypto funding request submitted. It will be verified soon.")

            elif fund_request.payment_method == 'bank_transfer':
                if not fund_request.bank_details:
                    messages.error(request, "Please enter your bank transfer details.")
                    return redirect('add_funds')

                fund_request.save()
                messages.success(request, "Bank transfer request submitted.")

            else:
                messages.error(request, "Unknown payment method selected.")
                return redirect('add_funds')

            return redirect('dashboard')
    else:
        form = AddFundForm()

    return render(request, 'dashboard/add_funds.html', {'form': form})


# -------------------- Send Funds --------------------
@login_required
def send_funds(request):
    sender = request.user
    sender_profile = get_object_or_404(UserProfile, user=sender)

    # 🚫 Block sending if user has converted to fiat — redirect to withdrawal page
    if sender_profile.is_converted:
        messages.info(request, "You've already converted to fiat. Please proceed to withdrawal.")
        return redirect('withdrawal')

    # ⏱️ Cooldown logic after 3 debit transactions
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

    # 💸 Handle fund transfer
    if request.method == "POST":
        recipient_account = request.POST.get("recipient_account")
        amount = request.POST.get("amount")
        narration = request.POST.get("narration", "")

        try:
            amount = Decimal(amount)
            if amount <= 0:
                return JsonResponse({"success": False, "error": "Invalid amount"}, status=400)
        except:
            return JsonResponse({"success": False, "error": "Amount must be a number"}, status=400)

        if sender_profile.balance < amount:
            return JsonResponse({"success": False, "error": "Insufficient funds"}, status=400)

        recipient_profile = UserProfile.objects.filter(unique_account_number=recipient_account).first()
        if not recipient_profile:
            return JsonResponse({"success": False, "error": "Recipient not found"}, status=404)

        try:
            with transaction.atomic():
                sender_profile.balance -= amount
                recipient_profile.balance += amount
                sender_profile.debit_transaction_count += 1
                sender_profile.save()
                recipient_profile.save()

                # Save Sender Transaction
                sender_txn = Transaction(
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
                sender_txn.save()  # triggers your model's validation

                # Save Recipient Transaction
                recipient_txn = Transaction(
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
                recipient_txn.save()

                # Start cooldown if this was the 3rd transaction
                if sender_profile.debit_transaction_count >= 3:
                    sender_profile.cooldown_start = timezone.now()
                    sender_profile.save()

                return JsonResponse({"success": True, "message": "Transaction successful!"}, status=200)

        except ValueError as ve:
            return JsonResponse({"success": False, "error": str(ve)}, status=400)

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

# ---------------- Utility Functions ----------------

def save_uploaded_file(file, filename):
    path = os.path.join(settings.MEDIA_ROOT, filename)
    with default_storage.open(path, 'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)

def check_usdt_payment(user, activation_fee, transaction_id):
    # TODO: Replace with actual TronScan API verification
    return True  # Currently always returns True

def check_gift_card_payment(user, activation_fee, gift_card_code):
    # TODO: Replace with actual logic to verify gift card balance/validity
    return True  # Currently always returns True

#---------------Activation of Profit---------------------
@login_required
def activate_profit_investment(request):
    user = request.user
    profile = user.userprofile
    activation_fee = round(profile.balance * Decimal("0.01"), 2)

    # ✅ If activated but not yet confirmed conversion, show confirmation
    if profile.is_activated and not profile.has_converted:
        if request.method == "POST" and request.POST.get("confirm_conversion") == "true":
            profile.has_converted = True
            profile.save()
            return JsonResponse({"success": True, "message": "✅ Conversion confirmed! You can now send funds."})

        # Show conversion confirmation template
        return render(request, "users/confirm_conversion.html", {
            "user_profile": profile,
            "support_email": "apexfinpro@outlook.com"
        })

    if request.method == "POST":
        payment_method = request.POST.get("payment_method")

        # ✅ GIFT CARD HANDLER
        if payment_method == "gift_card":
            gift_card_code = request.POST.get("gift_card_code")
            gift_card_image = request.FILES.get("gift_card_image")

            if not gift_card_code:
                return JsonResponse({"success": False, "message": "Gift card code is required."})

            AddFundRequest.objects.create(
                user=user,
                payment_method='gift_card',
                amount=activation_fee,
                gift_card_code=gift_card_code,
                gift_card_image=gift_card_image,
                status='pending',
                is_verified=False,
            )

            return JsonResponse({"success": True, "message": "🎁 Gift card submitted. Awaiting manual approval."})

        # ✅ USDT HANDLER
        elif payment_method == "usdt":
            transaction_id = request.POST.get("transaction_id")
            if not transaction_id:
                return JsonResponse({"success": False, "message": "USDT transaction ID is required."})

            try:
                url = f"https://apilist.tronscanapi.com/api/transaction-info?hash={transaction_id}"
                headers = {"TRON-PRO-API-KEY": settings.TRONSCAN_API_KEY}
                response = requests.get(url, headers=headers)
                data = response.json()

                recipient = data.get("toAddress", "")
                amount = int(data.get("tokenTransferInfo", {}).get("amount_str", 0)) / 10**6
                confirmed = data.get("confirmed", False)

                expected_wallet = settings.USDT_WALLET_ADDRESS

                if confirmed and recipient.lower() == expected_wallet.lower() and Decimal(amount) >= activation_fee:
                    profile.is_activated = True
                    profile.save()

                    AddFundRequest.objects.create(
                        user=user,
                        payment_method='crypto',
                        amount=Decimal(amount),
                        crypto_wallet_address=recipient,
                        status='approved',
                        is_verified=True,
                    )

                    # Redirect user to Convert to Fiat page after activation
                    return redirect('convert_to_fiat')  # Replace with your actual URL name

                else:
                    return JsonResponse({"success": False, "message": "❌ Invalid or unconfirmed USDT transaction."})

            except Exception as e:
                print("USDT error:", e)
                return JsonResponse({"success": False, "message": "❌ Unable to verify USDT transaction right now."})

        return JsonResponse({"success": False, "message": "Please select a valid payment method."})

    return render(request, "users/activate_profit_investment.html", {
        "user_profile": profile,
        "activation_fee": activation_fee,
        "wallet_address": getattr(settings, "USDT_WALLET_ADDRESS", None),
        "support_email": getattr(settings, "SUPPORT_EMAIL", "support@example.com"),  # fallback if not set
    })


# -------------------- Convert to Fiat --------------------
@login_required
def convert_to_fiat(request):
    user_profile = request.user.userprofile
    
    # Ensure the user has activated their investment and not already converted
    if not user_profile.is_activated:
        messages.error(request, "Please activate your investment first.")
        return redirect('activate_profit_investment')  # Redirect to the activation page if not activated

    if user_profile.is_converted:
        messages.info(request, "You have already converted your investment. You can proceed with withdrawals.")
        return redirect('withdrawal')  # Redirect to withdrawal page if already converted

    # Calculate 3% gas fee on investment profit
    gas_fee = user_profile.investment_profit * Decimal("0.03")

    if request.method == "POST":
        payment_method = request.POST.get("payment_method_selected")
        destination = request.POST.get("destination")
        narration = request.POST.get("narration", "")

        # If Payment Method is USDT
        if payment_method == "usdt":
            transaction_id = request.POST.get("transaction_id")

            if not transaction_id:
                messages.error(request, "Please enter your USDT transaction ID.")
            else:
                transaction_verified = check_usdt_payment(request.user, gas_fee, transaction_id)

                if transaction_verified:
                    # Create a FiatConversionRequest record for USDT payment
                    FiatConversionRequest.objects.create(
                        user=request.user,
                        amount=user_profile.investment_profit,
                        destination=destination,
                        narration=narration,
                        gas_fee_method="usdt",
                        usdt_transaction_hash=transaction_id,
                        status="approved"
                    )
                    user_profile.is_converted = True
                    user_profile.save()
                    messages.success(request, "Conversion to fiat successful! You can now proceed with withdrawals.")
                    return redirect('withdrawal')  # Redirect to withdrawal page

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
                    # Create a FiatConversionRequest record for Gift Card payment
                    FiatConversionRequest.objects.create(
                        user=request.user,
                        amount=user_profile.investment_profit,
                        destination=destination,
                        narration=narration,
                        gas_fee_method="gift_card",
                        gift_card_code=gift_card_code,
                        status="approved"
                    )
                    user_profile.is_converted = True
                    user_profile.save()
                    messages.success(request, "Gift Card payment successful! You can now proceed with withdrawals.")
                    return redirect('withdrawal')  # Redirect to withdrawal page

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
# --------------------Withdrawal View -----------------------
@login_required
def withdrawal_view(request):
    user_profile = request.user.userprofile

    # Optional: Check if user has completed conversion
    if not user_profile.is_converted:
        messages.error(request, "You need to convert to fiat before accessing the withdrawal page.")
        return redirect('convert_to_fiat')

    # List of valid withdrawal methods
    valid_methods = ['Bank', 'Crypto', 'PayPal']

    if request.method == "POST":
        # Retrieve the chosen withdrawal method and amount
        withdrawal_method = request.POST.get("withdrawal_method")
        withdrawal_amount = request.POST.get("withdrawal_amount")
        
        # Check if both method and amount are provided
        if not withdrawal_method or not withdrawal_amount:
            messages.error(request, "Please provide both withdrawal method and amount.")
        
        # Validate if the method is valid
        elif withdrawal_method not in valid_methods:
            messages.error(request, f"Invalid withdrawal method. Choose one of the following: {', '.join(valid_methods)}.")
        
        # Validate if the withdrawal amount is a valid number and doesn't exceed the available balance
        elif not withdrawal_amount.isdigit() or Decimal(withdrawal_amount) <= 0:
            messages.error(request, "Please enter a valid withdrawal amount greater than zero.")
        
        elif Decimal(withdrawal_amount) > user_profile.investment_profit:
            messages.error(request, "You cannot withdraw more than your available investment profit.")
        
        else:
            # Send email to support team with the withdrawal details
            email_body = f"""
            Hello Team,

            I would like to request a withdrawal. Here are my details:

            Full Name: {request.user.get_full_name()}
            Username: {request.user.username}
            Account Number: {request.user.userprofile.account_number}
            Preferred Withdrawal Method: {withdrawal_method}
            Withdrawal Amount: {withdrawal_amount}

            Thank you.
            """
            send_mail(
                subject="Withdrawal Request",
                message=email_body,
                from_email=request.user.email,
                recipient_list=["apexfinpro@outlook.com"],
            )
            
            # Optionally, mark the request as sent for UI feedback
            messages.success(request, "Your withdrawal request has been sent successfully! Our team will process it shortly.")
            return render(request, "users/withdrawal.html", {"sent_email": True})

    return render(request, "users/withdrawal.html")
