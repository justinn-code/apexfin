from django.contrib import admin
from .models import UserProfile, Transaction, UserLocation

class TransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "transaction_type", "timestamp")  # Show in admin table
    list_filter = ("transaction_type", "timestamp")
    search_fields = ("user__username", "amount")

admin.site.register(UserProfile)
admin.site.register(Transaction, TransactionAdmin)


# Register your models here.
