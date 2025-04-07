from django.contrib import admin
from django.utils.html import format_html
from .models import UserProfile, Transaction

class TransactionAdmin(admin.ModelAdmin):
    # Fields to display in the admin table
    list_display = (
        'user', 'transaction_type', 'amount', 'sender_name', 'sender_account',
        'recipient_name', 'recipient_account', 'timestamp', 'status', 'balance_after', 'get_transaction_direction'
    )

    # Add search functionality
    search_fields = ('user__username', 'sender_name', 'recipient_name', 'transaction_type')

    # Filter transactions by type and status
    list_filter = ('transaction_type', 'status', 'timestamp')

    # Order transactions by timestamp (descending)
    ordering = ['-timestamp']

    # Display transaction direction (Sent/Received)
    def get_transaction_direction(self, obj):
        return obj.get_transaction_direction(obj.user)
    get_transaction_direction.short_description = 'Transaction Direction'

    # Display the counterparty's name in the list view
    def get_counterparty_name(self, obj):
        return obj.get_counterparty_name(obj.user)
    get_counterparty_name.short_description = 'Counterparty'

    # Display the counterparty's account number
    def get_counterparty_account(self, obj):
        return obj.get_counterparty_account(obj.user)
    get_counterparty_account.short_description = 'Counterparty Account'

    # Optional: Use HTML formatting for the transaction status to make it easier to distinguish success/fail
    def status_html(self, obj):
        if obj.status == 'completed':
            return format_html('<span style="color: green; font-weight: bold;">{}</span>', obj.status)
        else:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', obj.status)
    status_html.short_description = 'Status'

    # Customize the form layout in the admin panel
    fieldsets = (
        (None, {
            'fields': ('user', 'transaction_type', 'amount', 'sender_name', 'sender_account',
                       'recipient_name', 'recipient_account', 'narration', 'status', 'balance_after')
        }),
        ('Timestamp and Additional Info', {
            'fields': ('timestamp',),
            'classes': ('collapse',),
        }),
    )

# Register the models in the admin panel
admin.site.register(UserProfile)
admin.site.register(Transaction, TransactionAdmin)
