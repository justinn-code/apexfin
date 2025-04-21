from django.contrib import admin
from django.utils.html import format_html
from django.urls import path
from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm

from .models import CustomUser, UserProfile, Transaction, AddFundRequest, GiftCard

User = get_user_model()


class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'transaction_type', 'amount', 'sender_name', 'sender_account',
        'recipient_name', 'recipient_account', 'timestamp', 'status_html', 'balance_after', 'get_transaction_direction'
    )
    search_fields = ('user__username', 'sender_name', 'recipient_name', 'transaction_type')
    list_filter = ('transaction_type', 'status', 'timestamp')
    ordering = ['-timestamp']

    def get_transaction_direction(self, obj):
        return obj.get_transaction_direction(obj.user)
    get_transaction_direction.short_description = 'Transaction Direction'

    def status_html(self, obj):
        color = "green" if obj.status == 'completed' else "red"
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, obj.status)
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
    change_list_template = "admin/addfund_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("review-fund-requests/", self.admin_site.admin_view(self.review_requests_view), name="review-fund-requests"),
            path("approve-fund-request/<int:request_id>/", self.admin_site.admin_view(self.approve_fund_request), name="approve-fund-request"),
            path("reject-fund-request/<int:request_id>/", self.admin_site.admin_view(self.reject_fund_request), name="reject-fund-request"),
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
            gift_card = GiftCard.objects.filter(code=fund_request.gift_card_code, is_valid=True).first()
            if gift_card:
                fund_request.status = 'approved'
                fund_request.is_verified = True
                fund_request.save()
                gift_card.delete()

                # ✅ Activate user profile
                profile = fund_request.user.profile
                profile.is_activated = True
                profile.save()

                messages.success(request, f"Gift card {gift_card.code} approved. User activated.")
            else:
                messages.error(request, f"No valid gift card found with code: {fund_request.gift_card_code}.")
                return redirect("admin:review-fund-requests")
        else:
            fund_request.status = 'approved'
            fund_request.is_verified = True
            fund_request.save()

            # ✅ Activate user profile
            profile = fund_request.user.profile
            profile.is_activated = True
            profile.save()

            messages.success(request, f"Fund request {fund_request.id} approved. User activated.")

        return redirect("admin:review-fund-requests")

    def reject_fund_request(self, request, request_id):
        fund_request = get_object_or_404(AddFundRequest, id=request_id)
        fund_request.status = 'rejected'
        fund_request.is_verified = False
        fund_request.save()
        messages.warning(request, f"Fund request {fund_request.id} rejected.")
        return redirect("admin:review-fund-requests")


class GiftCardAdmin(admin.ModelAdmin):
    list_display = ['code', 'value', 'user']
    search_fields = ('code', 'user__user__username')
    ordering = ['-value']


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    change_password_form = AdminPasswordChangeForm

    list_display = ('email', 'username', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    ordering = ('email',)

    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('your_extra_fields_here',)}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('your_extra_fields_here',)}),
    )


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'unique_account_number', 'balance', 'is_activated']
    list_filter = ['is_activated']
    search_fields = ['user__username', 'unique_account_number']


# ✅ Register admin models
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(AddFundRequest, AddFundRequestAdmin)
admin.site.register(GiftCard, GiftCardAdmin)
