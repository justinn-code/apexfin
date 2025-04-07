from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('', views.homepage, name='homepage'),  # Homepage
    path('signup/', views.signup_view, name='signup'),  # User Signup
    path('login/', views.login_view, name='login'),  # User Login
    path('logout/', views.logout_view, name='logout'),  # User Logout
    path('dashboard/', views.dashboard, name='dashboard'),  # User Dashboard
    path('fund-account/', views.fund_account, name='fund_account'),  # Fund Account
    path('send-funds/', views.send_funds, name='send_funds'),  # Send Funds
    path('get-recipient-name/', views.get_recipient_name, name='get_recipient_name'),  # <-- New API
    path('receive-funds/', views.receive_funds, name='receive_funds'),  # Receive Funds
    path('transaction-history/', views.transaction_history, name='transaction_history'),  # Transaction History
    path('activate-profit-investment/', views.activate_profit_investment, name='activate_profit_investment'),  # Activate ApexFin Coin
    path('cooldown-message/', views.cooldown_message, name='cooldown_message'),  # Cooldown Message
    path('convert-to-fiat/', views.convert_to_fiat, name='convert_to_fiat'),  # Convert ApexFin Coin to fiat (3% gas fee)
    path('all-users/', views.all_users, name='all_users'),  # View All Users (Admin or Special Access)
]
