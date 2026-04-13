from django.contrib import admin

from .models import CashBalance, CashGapAlert


@admin.register(CashBalance)
class CashBalanceAdmin(admin.ModelAdmin):
    list_display = [
        "date", "opening_balance", "total_inflow", "total_outflow",
        "closing_balance", "is_cash_gap",
    ]
    list_filter = ["is_cash_gap"]
    date_hierarchy = "date"


@admin.register(CashGapAlert)
class CashGapAlertAdmin(admin.ModelAdmin):
    list_display = ["date", "deficit_amount", "is_acknowledged", "acknowledged_by", "created_at"]
    list_filter = ["is_acknowledged"]
    date_hierarchy = "date"
