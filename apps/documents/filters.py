import django_filters

from .models import GoodsReceipt, Invoice, PaymentOrder


class GoodsReceiptFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte", label="Дата с")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte", label="Дата по")
    counterparty = django_filters.NumberFilter(field_name="counterparty_id")
    is_paid = django_filters.BooleanFilter()
    search = django_filters.CharFilter(method="filter_search", label="Поиск")

    class Meta:
        model = GoodsReceipt
        fields = ["counterparty", "is_paid"]

    def filter_search(self, queryset, name, value):
        from django.db.models import Q

        return queryset.filter(
            Q(number__icontains=value) | Q(counterparty__name__icontains=value)
        )


class PaymentOrderFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    counterparty = django_filters.NumberFilter(field_name="counterparty_id")

    class Meta:
        model = PaymentOrder
        fields = ["counterparty"]


class InvoiceFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")
    direction = django_filters.ChoiceFilter(choices=Invoice.Direction.choices)
    is_paid = django_filters.BooleanFilter()

    class Meta:
        model = Invoice
        fields = ["direction", "is_paid"]
