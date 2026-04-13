import django_tables2 as tables

from .models import GoodsReceipt, Invoice, PaymentOrder


class GoodsReceiptTable(tables.Table):
    number = tables.LinkColumn(
        "documents:receipt_detail", args=[tables.A("pk")], verbose_name="Номер"
    )
    date = tables.DateColumn(format="d.m.Y", verbose_name="Дата")
    counterparty = tables.Column(verbose_name="Контрагент")
    amount = tables.Column(verbose_name="Сумма")
    payment_due_date = tables.DateColumn(format="d.m.Y", verbose_name="Срок оплаты")
    is_paid = tables.BooleanColumn(verbose_name="Оплачен")

    class Meta:
        model = GoodsReceipt
        fields = ["number", "date", "counterparty", "amount", "payment_due_date", "is_paid"]
        template_name = "django_tables2/bootstrap5.html"
        attrs = {"class": "table table-hover table-sm"}
        order_by = "-date"


class PaymentOrderTable(tables.Table):
    number = tables.Column(verbose_name="Номер")
    date = tables.DateColumn(format="d.m.Y", verbose_name="Дата")
    counterparty = tables.Column(verbose_name="Контрагент")
    amount = tables.Column(verbose_name="Сумма")

    class Meta:
        model = PaymentOrder
        fields = ["number", "date", "counterparty", "amount"]
        template_name = "django_tables2/bootstrap5.html"
        attrs = {"class": "table table-hover table-sm"}
        order_by = "-date"


class InvoiceTable(tables.Table):
    number = tables.Column(verbose_name="Номер")
    date = tables.DateColumn(format="d.m.Y", verbose_name="Дата")
    counterparty = tables.Column(verbose_name="Контрагент")
    direction = tables.Column(verbose_name="Направление")
    amount = tables.Column(verbose_name="Сумма")
    is_paid = tables.BooleanColumn(verbose_name="Оплачен")

    class Meta:
        model = Invoice
        fields = ["number", "date", "counterparty", "direction", "amount", "is_paid"]
        template_name = "django_tables2/bootstrap5.html"
        attrs = {"class": "table table-hover table-sm"}
        order_by = "-date"
