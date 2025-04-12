from django.urls import path
from . import views
from .views import review_add_fund_requests

app_name = 'users'

urlpatterns = [
    path('', views.homepage, name='homepage'),  # Homepage will now live at /users/
    path('admin/review-add-funds/', review_add_fund_requests, name='review_add_fund_requests'),
    path('add-funds/', views.add_funds, name='add_funds'),  # Add Funds
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('fund-account/', views.fund_account, name='fund_account'),
    path('send-funds/', views.send_funds, name='send_funds'),
    path('add-funds/', views.add_funds, name='add_funds'),
    path('get-recipient-name/', views.get_recipient_name, name='get_recipient_name'),
    path('receive-funds/', views.receive_funds, name='receive_funds'),
    path('transaction-history/', views.transaction_history, name='transaction_history'),
    path('activate-profit-investment/', views.activate_profit_investment, name='activate_profit_investment'),
    path('cooldown-message/', views.cooldown_message, name='cooldown_message'),
    path('convert-to-fiat/', views.convert_to_fiat, name='convert_to_fiat'),
    path('all-users/', views.all_users, name='all_users'),
]
