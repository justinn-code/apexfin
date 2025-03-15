from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.timezone import now, timedelta
from django.http import JsonResponse
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from decimal import Decimal  # ✅ For precise calculations
from .models import UserProfile, Transaction, calculate_investment_profit
from services.usdt_verification import verify_usdt_payment

# ✅ Homepage View
def homepage(request):
    if request.user.is_authenticated:
        return redirect('users:dashboard')
    return render(request, 'users/homepage.html')

# ✅ Signup View
def signup(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if not username or not email or not password:
            messages.error(request, "All fields are required.")
            return redirect("users:signup")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("users:signup")

        if User.objects.filter(email=email).exists():
            messages.error(request, "An account with this email already exists.")
            return redirect("users:signup")

        user = User.objects.create_user(username=username, email=email, password=password)
        UserProfile.objects.create(user=user)  # ✅ Create UserProfile

        login(request, user)  # ✅ Auto-login after signup
        return redirect("users:dashboard")

    return render(request, "users/signup.html")

# ✅ Fetch All Users (For Admin)
@login_required
def all_users(request):
    users = User.objects.all()
    return render(request, "users/all_users.html", {"users": users})

# ✅ Fund User Account (Admin Only)
@login_required
def fund_account(request):
    if request.method == "POST":
        username = request.POST["username"]
        amount = request.POST["amount"]

        if not username or not amount:
            messages.error(request, "All fields are required.")
            return redirect("users:fund_account")

        try:
            amount = Decimal(amount)  # ✅ Convert to Decimal
            if amount <= 0:
                messages.error(request, "Invalid amount.")
                return redirect("users:fund_account")

            user = User.objects.get(username=username)
            profile = user.userprofile
            profile.balance += amount
            profile.save()
            messages.success(request, f"Successfully added ${amount} to {username}'s account.")
        except User.DoesNotExist:
            messages.error(request, "User not found.")

    return render(request, "users/fund_account.html")

# ✅ User Dashboard
@login_required
def dashboard(request):
    profile = request.user.userprofile
    transactions = Transaction.objects.filter(user=request.user).order_by('-timestamp')
    investment_profit = calculate_investment_profit(request.user)
    transaction_count = transactions.count()
    cooldown_expired = True
    cooldown_remaining = 0
    activation_required = False

    if transaction_count >= 3 and not profile.is_activated:
        if not profile.cooldown_start:
            profile.cooldown_start = now()
            profile.save()
        cooldown_end = profile.cooldown_start + timedelta(hours=36)
        cooldown_remaining = (cooldown_end - now()).total_seconds()
        cooldown_expired = cooldown_remaining <= 0
        activation_required = cooldown_expired

    context = {
        'profile': profile,
        'transactions': transactions,
        'investment_profit': investment_profit,
        'transaction_count': transaction_count,
        'cooldown_expired': cooldown_expired,
        'cooldown_remaining': cooldown_remaining,
        'activation_required': activation_required,
        'user_name': request.user.get_full_name() or request.user.username,
        'account_number': profile.unique_account_number,
        'balance': profile.balance,
    }
    return render(request, 'users/dashboard.html', context)

# ✅ Transaction History
@login_required
def transaction_history(request):
    transactions = Transaction.objects.filter(user=request.user).order_by('-timestamp')
    return render(request, 'users/transaction_history.html', {'transactions': transactions})

# ✅ Receive Funds
@login_required
def receive_funds(request):
    profile = request.user.userprofile
    return render(request, 'users/receive_funds.html', {'account_number': profile.unique_account_number})

# ✅ USDT Activation Payment
@login_required
def activate_apexfin_coin(request):
    profile = request.user.userprofile
    if profile.is_activated:
        return JsonResponse({'status': 'already_activated'})

    expected_amount = profile.balance * Decimal(0.01)
    txn_hash = request.GET.get('txn_hash')

    if not txn_hash:
        return JsonResponse({'status': 'error', 'message': 'Transaction hash required'})

    success, error_message = verify_usdt_payment(txn_hash, expected_amount)
    if success:
        profile.is_activated = True
        profile.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error', 'message': error_message})

# ✅ Send Funds
@login_required
def send_funds(request):
    sender_profile = request.user.userprofile

    if request.method == "POST":
        recipient_account = request.POST.get("recipient_account")
        amount = request.POST.get("amount")
        narration = request.POST.get("narration", "")

        if not recipient_account or not amount:
            messages.error(request, "All fields are required.")
            return redirect('users:send_funds')

        try:
            amount = Decimal(amount)  # Convert amount to Decimal
            if amount <= 0:
                messages.error(request, "Invalid amount.")
                return redirect('users:send_funds')
        except:
            messages.error(request, "Enter a valid numeric amount.")
            return redirect('users:send_funds')

        # Check if sender has enough balance
        if sender_profile.balance < amount:
            messages.error(request, "Insufficient balance.")
            return redirect('users:send_funds')

        try:
            recipient_profile = UserProfile.objects.get(unique_account_number=recipient_account)

            # Deduct from sender and add to recipient
            sender_profile.balance -= amount
            recipient_profile.balance += amount
            sender_profile.save()
            recipient_profile.save()

            # ✅ Fix sender/receiver fields
            Transaction.objects.create(
                user=request.user,  # Link transaction to the sender user
                sender=sender_profile,  # Save sender profile
                receiver=recipient_profile,  # Save receiver profile
                amount=amount,
                narration=narration
            )

            messages.success(request, f"Transaction successful! Sent ${amount} to {recipient_profile.user.username}.")
            return redirect("users:dashboard")

        except UserProfile.DoesNotExist:
            messages.error(request, "Invalid account number.")
            return redirect('users:send_funds')

    return render(request, 'users/send_funds.html')

# ✅ Check USDT Payment Status
@login_required
def check_usdt_payment(request):
    txn_hash = request.GET.get("txn_hash")
    amount = request.GET.get("amount")

    if not txn_hash or not amount:
        return JsonResponse({"status": "error", "message": "Transaction hash and amount required"})

    try:
        amount = float(amount)
    except ValueError:
        return JsonResponse({"status": "error", "message": "Invalid amount format"})

    success, error_message = verify_usdt_payment(txn_hash, amount)

    if success:
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error", "message": error_message})

# ✅ Cooldown Status
@login_required
def cooldown_status(request):
    profile = request.user.userprofile
    if not profile.cooldown_start:
        return JsonResponse({"status": "expired"})

    cooldown_end = profile.cooldown_start + timedelta(hours=36)
    cooldown_remaining = (cooldown_end - now()).total_seconds()

    if cooldown_remaining <= 0:
        return JsonResponse({"status": "expired"})

    return JsonResponse({"status": "active", "remaining_time": cooldown_remaining})
