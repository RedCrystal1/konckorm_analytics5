import django_filters
from django.db.models import Q

from .models import DebtByTerms, PlannedPayment


class DebtByTermsFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=DebtByTerms.DebtStatus.choices,
        empty_label="Все",
    )
    counterparty = django_filters.NumberFilter(field_name="counterparty_id")
    responsible_manager = django_filters.NumberFilter(field_name="responsible_manager_id")
    date_from = django_filters.DateFilter(
        field_name="planned_payment_date", lookup_expr="gte"
    )
    date_to = django_filters.DateFilter(
        field_name="planned_payment_date", lookup_expr="lte"
    )
    search = django_filters.CharFilter(method="filter_search", label="Поиск")

    class Meta:
        model = DebtByTerms
        fields = ["status", "counterparty", "responsible_manager"]

    def filter_search(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(counterparty__name__icontains=value)
                | Q(source_document__number__icontains=value)
            )
        return queryset


class PlannedPaymentFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=PlannedPayment.PaymentStatus.choices)
    priority = django_filters.ChoiceFilter(choices=PlannedPayment.Priority.choices)
    date_from = django_filters.DateFilter(field_name="planned_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="planned_date", lookup_expr="lte")

    class Meta:
        model = PlannedPayment
        fields = ["status", "priority"]