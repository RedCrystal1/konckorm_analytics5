import django_tables2 as tables

from .models import Contract, Counterparty


class CounterpartyTable(tables.Table):
    name = tables.LinkColumn(
        "counterparties:detail",
        args=[tables.A("pk")],
        verbose_name="Наименование",
    )
    inn = tables.Column(verbose_name="ИНН")
    is_key_supplier = tables.BooleanColumn(verbose_name="Ключевой")
    responsible_manager = tables.Column(verbose_name="Менеджер")
    is_active = tables.BooleanColumn(verbose_name="Активен")

    class Meta:
        model = Counterparty
        fields = ["name", "inn", "is_key_supplier", "responsible_manager", "is_active"]
        template_name = "django_tables2/bootstrap5.html"
        attrs = {"class": "table table-hover table-sm"}
        order_by = "name"


class ContractTable(tables.Table):
    number = tables.LinkColumn(
        "counterparties:contract_detail",
        args=[tables.A("pk")],
        verbose_name="Номер",
    )
    counterparty = tables.Column(verbose_name="Контрагент")
    date = tables.DateColumn(format="d.m.Y", verbose_name="Дата")
    kind = tables.Column(verbose_name="Вид")
    payment_term_type = tables.Column(verbose_name="Условия оплаты")
    payment_days = tables.Column(verbose_name="Срок (дн.)")
    is_active = tables.BooleanColumn(verbose_name="Активен")

    class Meta:
        model = Contract
        fields = [
            "number",
            "counterparty",
            "date",
            "kind",
            "payment_term_type",
            "payment_days",
            "is_active",
        ]
        template_name = "django_tables2/bootstrap5.html"
        attrs = {"class": "table table-hover table-sm"}
        order_by = "-date"
