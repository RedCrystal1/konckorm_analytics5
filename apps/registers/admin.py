from django.contrib import admin

from .models import (
    ContractConditionHistory,
    DebtByTerms,
    PlannedPayment,
    ProcurementVolume,
)


@admin.register(DebtByTerms)
class DebtByTermsAdmin(admin.ModelAdmin):
    list_display = [
        "counterparty",
        "status",
        "amount_rub",
        "overdue_amount",
        "overdue_days",
        "planned_payment_date",
        "record_date",
    ]
    list_filter = ["status", "record_date"]
    search_fields = ["counterparty__name"]
    raw_id_fields = ["counterparty", "contract", "source_document"]


@admin.register(ProcurementVolume)
class ProcurementVolumeAdmin(admin.ModelAdmin):
    list_display = [
        "counterparty",
        "period_type",
        "period_start",
        "period_end",
        "procurement_kind",
        "volume_rub",
        "share_percent",
    ]
    list_filter = ["period_type", "procurement_kind"]
    search_fields = ["counterparty__name"]
    raw_id_fields = ["counterparty", "contract"]


@admin.register(PlannedPayment)
class PlannedPaymentAdmin(admin.ModelAdmin):
    list_display = [
        "counterparty",
        "planned_date",
        "amount",
        "status",
        "priority",
        "actual_date",
        "deviation_days",
    ]
    list_filter = ["status", "priority", "planned_date"]
    search_fields = ["counterparty__name"]
    raw_id_fields = ["counterparty", "contract", "source_document"]
    date_hierarchy = "planned_date"


@admin.register(ContractConditionHistory)
class ContractConditionHistoryAdmin(admin.ModelAdmin):
    list_display = [
        "contract",
        "valid_from",
        "valid_to",
        "payment_term_type",
        "payment_days",
        "credit_limit",
    ]
    list_filter = ["payment_term_type"]
    raw_id_fields = ["counterparty", "contract"]
