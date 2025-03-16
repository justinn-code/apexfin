from django.urls import path
from django.contrib.auth import views as auth_views
from . import views  # Ensure views module is imported

app_name = 'users'  # Namespace for URL reversing

urlpatterns = [
    # Homepage
    path('', views.homepage, name='homepage'),

    # Signup
    path('signup/', views.signup, name='signup'),
    
    # All Users
    path("all-users/", views.all_users, name="all_users"),

    # Funding Account
    path("fund-account/", views.fund_account, name="fund_account"),

    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Transactions
    path('receive/', views.receive_funds, name='receive_funds'),
    path('send/', views.send_funds, name='send_funds'),
    path('transactions/', views.transaction_history, name='transaction_history'),

    # ApexFin Coin Activation
    path('activate/', views.activate_apexfin_coin, name='activate_apexfin_coin'),
   
    # Authentication (Fixed Logout Redirect)
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='users:homepage'), name='logout'),

    # USDT Payment Verification
    path('check-usdt-payment/', views.verify_usdt_payment, name='check_usdt_payment'),
]
