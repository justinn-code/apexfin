from django.contrib import admin
from django.utils.html import format_html
from django.urls import path  # Required for custom admin URLs
from django.template.response import TemplateResponse  # Required for custom admin views
from django.shortcuts import get_object_or_404, redirect

from .models import UserProfile, Transaction, AddFundRequest  # Adjust path if needed


class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'transaction_type', 'amount', 'sender_name', 'sender_account',
        'recipient_name', 'recipient_account', 'timestamp', 'status', 'balance_after', 'get_transaction_direction'
    )
    search_fields = ('user__username', 'sender_name', 'recipient_name', 'transaction_type')
    list_filter = ('transaction_type', 'status', 'timestamp')
    ordering = ['-timestamp']

    def get_transaction_direction(self, obj):
        return obj.get_transaction_direction(obj.user)
    get_transaction_direction.short_description = 'Transaction Direction'

    def get_counterparty_name(self, obj):
        return obj.get_counterparty_name(obj.user)
    get_counterparty_name.short_description = 'Counterparty'

    def get_counterparty_account(self, obj):
        return obj.get_counterparty_account(obj.user)
    get_counterparty_account.short_description = 'Counterparty Account'

    def status_html(self, obj):
        if obj.status == 'completed':
            return format_html('<span style="color: green; font-weight: bold;">{}</span>', obj.status)
        else:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', obj.status)
    status_html.short_description = 'Status'

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


class AddFundRequestAdmin(admin.ModelAdmin):
    change_list_template = "admin/addfund_changelist.html"  # Optional custom template

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "review-fund-requests/",
                self.admin_site.admin_view(self.review_requests_view),
                name="review-fund-requests",
            ),
            path(
                "approve-fund-request/<int:request_id>/",
                self.admin_site.admin_view(self.approve_fund_request),
                name="approve-fund-request",
            ),
            path(
                "reject-fund-request/<int:request_id>/",
                self.admin_site.admin_view(self.reject_fund_request),
                name="reject-fund-request",
            ),
        ]
        return custom_urls + urls

    def review_requests_view(self, request):
        requests = AddFundRequest.objects.all().order_by("-created_at")
        return TemplateResponse(request, "admin/review_add_fund_requests.html", {
            "requests": requests,
            "title": "Review Add Fund Requests"
        })

    def approve_fund_request(self, request, request_id):
        fund_request = get_object_or_404(AddFundRequest, id=request_id)
        
        if fund_request.payment_method == 'gift_card':
            if fund_request.is_verified:
                if self.verify_gift_card_code(fund_request.gift_card_code):
                    fund_request.status = 'approved'
                    self.message_user(request, f"Gift card payment {fund_request.id} approved!")
                else:
                    fund_request.status = 'rejected'
                    self.message_user(request, f"Invalid gift card code {fund_request.gift_card_code}. Fund request rejected.")
            else:
                self.message_user(request, f"Gift card {fund_request.gift_card_code} not verified yet.")
                return redirect("admin:review-fund-requests")
        else:
            fund_request.status = 'approved'
            self.message_user(request, f"Fund request {fund_request.id} approved!")

        fund_request.save()
        return redirect("admin:review-fund-requests")

    def reject_fund_request(self, request, request_id):
        fund_request = get_object_or_404(AddFundRequest, id=request_id)
        fund_request.status = 'rejected'
        fund_request.save()
        self.message_user(request, f"Fund request {fund_request.id} rejected!")
        return redirect("admin:review-fund-requests")

    def verify_gift_card_code(self, code):
        valid_codes = ['GIFT123', 'DISCOUNT456', 'SPECIAL789']  # Placeholder for verification logic
        return code in valid_codes


# Register models
admin.site.register(UserProfile)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(AddFundRequest, AddFundRequestAdmin)
