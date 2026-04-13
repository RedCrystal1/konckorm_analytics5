import django_tables2 as tables

from .models import DebtByTerms, PlannedPayment


class DebtByTermsTable(tables.Table):
    counterparty = tables.Column(verbose_name="Контрагент")
    source_document = tables.Column(verbose_name="Документ")
    planned_payment_date = tables.DateColumn(format="d.m.Y", verbose_name="Срок оплаты")
    status = tables.Column(verbose_name="Статус")
    amount_rub = tables.Column(verbose_name="Сумма (руб.)")
    overdue_amount = tables.Column(verbose_name="Просрочка")
    overdue_days = tables.Column(verbose_name="Дней")
    responsible_manager = tables.Column(verbose_name="Менеджер")

    class Meta:
        model = DebtByTerms
        fields = [
            "counterparty",
            "source_document",
            "planned_payment_date",
            "status",
            "amount_rub",
            "overdue_amount",
            "overdue_days",
            "responsible_manager",
        ]
        template_name = "django_tables2/bootstrap5.html"
        attrs = {"class": "table table-hover table-sm"}
        order_by = "-overdue_days"

    def render_status(self, value, record):
        status_colors = {
            "current": "success",
            "overdue_30": "warning",
            "overdue_60": "warning",
            "overdue_90": "danger",
            "overdue_90_plus": "danger",
            "doubtful": "dark",
        }
        color = status_colors.get(record.status, "secondary")
        return tables.utils.AttributeDict({"class": f"badge bg-{color}"})


class PlannedPaymentTable(tables.Table):
    counterparty = tables.Column(verbose_name="Контрагент")
    planned_date = tables.DateColumn(format="d.m.Y", verbose_name="Плановая дата")
    amount = tables.Column(verbose_name="Сумма")
    status = tables.Column(verbose_name="Статус")
    priority = tables.Column(verbose_name="Приоритет")

    class Meta:
        model = PlannedPayment
        fields = ["counterparty", "planned_date", "amount", "status", "priority"]
        template_name = "django_tables2/bootstrap5.html"
        attrs = {"class": "table table-hover table-sm"}
        order_by = "planned_date"
