import django_filters

from .models import Contract, Counterparty


class CounterpartyFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(
        method="filter_search",
        label="Поиск",
    )
    is_key_supplier = django_filters.BooleanFilter(
        field_name="is_key_supplier",
        label="Ключевой поставщик",
    )
    is_active = django_filters.BooleanFilter(
        field_name="is_active",
        label="Активен",
    )
    responsible_manager = django_filters.NumberFilter(
        field_name="responsible_manager_id",
        label="Ответственный менеджер",
    )

    class Meta:
        model = Counterparty
        fields = ["is_key_supplier", "is_active", "responsible_manager"]

    def filter_search(self, queryset, name, value):
        if value:
            return queryset.filter(
                models_Q(name__icontains=value)
                | models_Q(inn__icontains=value)
                | models_Q(full_name__icontains=value)
                | models_Q(code_1c__icontains=value)
            )
        return queryset


class ContractFilter(django_filters.FilterSet):
    counterparty = django_filters.NumberFilter(field_name="counterparty_id")
    kind = django_filters.ChoiceFilter(choices=Contract.Kind.choices)
    is_active = django_filters.BooleanFilter()
    date_from = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = Contract
        fields = ["counterparty", "kind", "is_active"]


from django.db.models import Q as models_Q  # noqa: E402
