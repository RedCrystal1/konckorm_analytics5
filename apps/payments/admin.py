from django.contrib import admin

from .models import CashBalance, CashGapAlert, PaymentRequest, PaymentRequestHistory


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


class PaymentRequestHistoryInline(admin.TabularInline):
    """Инлайн с историей переходов прямо в карточке заявки."""
    model = PaymentRequestHistory
    extra = 0
    readonly_fields = ["from_status", "to_status", "actor", "comment", "created_at"]
    can_delete = False
    ordering = ["-created_at"]
    fields = ["created_at", "from_status", "to_status", "actor", "comment"]


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = [
        "id", "counterparty", "amount", "planned_date",
        "status", "priority", "created_by", "reviewed_by", "created_at",
    ]
    list_filter = ["status", "priority", "currency"]
    search_fields = [
        "counterparty__name", "counterparty__inn",
        "purpose", "one_c_doc_number", "one_c_doc_key",
    ]
    date_hierarchy = "created_at"
    readonly_fields = [
        "created_at", "updated_at", "submitted_at", "reviewed_at",
        "sent_to_1c_at", "one_c_doc_key", "one_c_doc_number",
    ]
    fieldsets = (
        ("Стороны и связи", {
            "fields": ("counterparty", "contract", "related_receipt"),
        }),
        ("Платёж", {
            "fields": ("amount", "currency", "planned_date", "purpose", "priority"),
        }),
        ("Workflow", {
            "fields": (
                "status", "created_by", "submitted_at",
                "reviewed_by", "reviewed_at", "rejection_reason",
            ),
        }),
        ("Интеграция с 1С", {
            "fields": (
                "one_c_doc_key", "one_c_doc_number",
                "sent_to_1c_at", "one_c_error",
            ),
            "classes": ("collapse",),
        }),
        ("Служебное", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    inlines = [PaymentRequestHistoryInline]


@admin.register(PaymentRequestHistory)
class PaymentRequestHistoryAdmin(admin.ModelAdmin):
    list_display = ["request", "from_status", "to_status", "actor", "created_at"]
    list_filter = ["from_status", "to_status"]
    search_fields = ["request__id", "actor__username", "comment"]
    date_hierarchy = "created_at"
    readonly_fields = ["request", "from_status", "to_status", "actor", "comment", "created_at"]
