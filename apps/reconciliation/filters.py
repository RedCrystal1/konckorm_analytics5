import django_filters

from .models import Discrepancy


class DiscrepancyFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=Discrepancy.Status.choices)
    reason = django_filters.ChoiceFilter(choices=Discrepancy.Reason.choices)
    counterparty = django_filters.NumberFilter(field_name="counterparty_id")
    search = django_filters.CharFilter(method="filter_search", label="Поиск")

    class Meta:
        model = Discrepancy
        fields = ["status", "reason", "counterparty"]

    def filter_search(self, queryset, name, value):
        from django.db.models import Q

        return queryset.filter(
            Q(document_ref__icontains=value) | Q(counterparty__name__icontains=value)
        )
