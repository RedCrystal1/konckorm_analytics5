from django.contrib import admin

from .models import (
    AccountBalance,
    GoodsReceipt,
    GoodsReceiptItem,
    Invoice,
    PaymentOrder,
)


class GoodsReceiptItemInline(admin.TabularInline):
    model = GoodsReceiptItem
    extra = 0


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "date",
        "counterparty",
        "amount",
        "payment_due_date",
        "is_paid",
        "paid_amount",
    ]
    list_filter = ["is_paid", "date"]
    search_fields = ["number", "counterparty__name"]
    raw_id_fields = ["counterparty", "contract"]
    date_hierarchy = "date"
    inlines = [GoodsReceiptItemInline]


@admin.register(PaymentOrder)
class PaymentOrderAdmin(admin.ModelAdmin):
    list_display = ["number", "date", "counterparty", "amount"]
    list_filter = ["date"]
    search_fields = ["number", "counterparty__name"]
    raw_id_fields = ["counterparty", "contract", "related_receipt"]
    date_hierarchy = "date"


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "date",
        "counterparty",
        "direction",
        "amount",
        "is_paid",
    ]
    list_filter = ["direction", "is_paid", "date"]
    search_fields = ["number", "counterparty__name"]
    raw_id_fields = ["counterparty", "contract"]
    date_hierarchy = "date"


@admin.register(AccountBalance)
class AccountBalanceAdmin(admin.ModelAdmin):
    list_display = [
        "account",
        "counterparty",
        "balance_date",
        "debit",
        "credit",
        "balance",
    ]
    list_filter = ["account", "balance_date"]
    search_fields = ["counterparty__name"]
    raw_id_fields = ["counterparty", "contract"]
