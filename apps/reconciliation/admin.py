from django.contrib import admin

from .models import Discrepancy, ReconciliationAct


class DiscrepancyInline(admin.TabularInline):
    model = Discrepancy
    extra = 0
    fields = ["document_ref", "our_amount", "their_amount", "discrepancy_amount", "reason", "status"]


@admin.register(ReconciliationAct)
class ReconciliationActAdmin(admin.ModelAdmin):
    list_display = [
        "counterparty",
        "period_start",
        "period_end",
        "our_balance",
        "their_balance",
        "is_matched",
        "created_by",
    ]
    list_filter = ["is_matched", "period_end"]
    search_fields = ["counterparty__name"]
    raw_id_fields = ["counterparty"]
    inlines = [DiscrepancyInline]


@admin.register(Discrepancy)
class DiscrepancyAdmin(admin.ModelAdmin):
    list_display = [
        "document_ref",
        "counterparty",
        "our_amount",
        "their_amount",
        "discrepancy_amount",
        "reason",
        "status",
        "responsible",
    ]
    list_filter = ["status", "reason"]
    search_fields = ["document_ref", "counterparty__name"]
    raw_id_fields = ["counterparty", "reconciliation_act"]
