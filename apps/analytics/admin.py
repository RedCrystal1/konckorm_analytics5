from django.contrib import admin

from .models import AnalyticsSnapshot


@admin.register(AnalyticsSnapshot)
class AnalyticsSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        "date",
        "total_debt",
        "overdue_debt",
        "overdue_ratio",
        "turnover_days",
        "payment_ratio",
        "calculated_at",
    ]
    date_hierarchy = "date"
    readonly_fields = [
        "date", "total_debt", "overdue_debt", "overdue_ratio",
        "turnover_days", "payment_ratio", "avg_payment_days",
        "avg_deviation_days", "key_supplier_share",
        "forecast_cash_need_week", "forecast_cash_need_month",
        "cash_gap_probability", "calculated_at",
    ]

    def has_add_permission(self, request):
        return False
