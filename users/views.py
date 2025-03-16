from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.timezone import now, timedelta
from django.http import JsonResponse
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from decimal import Decimal
from .models import UserProfile, Transaction, calculate_investment_profit
from services.usdt_verification import verify_usdt_payment

def homepage(request):
    if request.user.is_authenticated:
        return redirect('users:dashboard')
    return render(request, 'users/homepage.html')

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
        UserProfile.objects.create(user=user)

        login(request, user)
        return redirect("users:dashboard")

    return render(request, "users/signup.html")

@login_required
def all_users(request):
    users = User.objects.all()
    return render(request, "users/all_users.html", {"users": users})

@login_required
def fund_account(request):
    if request.method == "POST":
        username = request.POST.get("username")
        amount = request.POST.get("amount")

        if not username or not amount:
            messages.error(request, "All fields are required.")
            return redirect("users:fund_account")

        try:
            amount = Decimal(amount)
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
        cooldown_remaining = max(0, (cooldown_end - now()).total_seconds())
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

@login_required
def transaction_history(request):
    transactions = Transaction.objects.filter(user=request.user).order_by('-timestamp')
    return render(request, 'users/transaction_history.html', {'transactions': transactions})

@login_required
def receive_funds(request):
    profile = request.user.userprofile
    return render(request, 'users/receive_funds.html', {'account_number': profile.unique_account_number})

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
            amount = Decimal(amount)
            if amount <= 0:
                messages.error(request, "Invalid amount.")
                return redirect('users:send_funds')
        except:
            messages.error(request, "Enter a valid numeric amount.")
            return redirect('users:send_funds')

        gas_fee = amount * Decimal(0.03)
        total_deduction = amount + gas_fee

        if sender_profile.balance < total_deduction:
            messages.error(request, f"Insufficient balance. A 3% gas fee applies (${gas_fee:.2f}).")
            return redirect('users:send_funds')

        try:
            recipient_profile = UserProfile.objects.get(unique_account_number=recipient_account)
            if recipient_profile == sender_profile:
                messages.error(request, "You cannot send funds to yourself.")
                return redirect('users:send_funds')

            sender_profile.balance -= total_deduction
            recipient_profile.balance += amount
            sender_profile.save()
            recipient_profile.save()

            Transaction.objects.create(user=request.user, sender=sender_profile, receiver=recipient_profile, amount=amount, narration=narration)

            messages.success(request, f"Transaction successful! Sent ${amount:.2f} to {recipient_profile.user.username} (Gas Fee: ${gas_fee:.2f}).")
            return redirect("users:dashboard")
        except UserProfile.DoesNotExist:
            messages.error(request, "Invalid account number.")
            return redirect('users:send_funds')

    return render(request, 'users/send_funds.html')
