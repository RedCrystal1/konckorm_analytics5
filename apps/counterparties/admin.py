from django.contrib import admin

from .models import Contract, Counterparty, CounterpartyHistorySnapshot


class ContractInline(admin.TabularInline):
    model = Contract
    extra = 0
    fields = ["number", "date", "kind", "payment_term_type", "payment_days", "is_active"]


@admin.register(Counterparty)
class CounterpartyAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "inn",
        "is_key_supplier",
        "responsible_manager",
        "is_active",
    ]
    list_filter = ["is_key_supplier", "is_active"]
    search_fields = ["name", "full_name", "inn", "code_1c"]
    inlines = [ContractInline]


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = [
        "number",
        "counterparty",
        "date",
        "kind",
        "payment_term_type",
        "payment_days",
        "is_active",
    ]
    list_filter = ["kind", "payment_term_type", "is_active", "currency"]
    search_fields = ["number", "name", "counterparty__name"]
    raw_id_fields = ["counterparty"]
    date_hierarchy = "date"


@admin.register(CounterpartyHistorySnapshot)
class CounterpartyHistorySnapshotAdmin(admin.ModelAdmin):
    list_display = ["counterparty", "snapshot_date", "changed_by"]
    list_filter = ["snapshot_date"]
    raw_id_fields = ["counterparty"]
    readonly_fields = ["data"]
