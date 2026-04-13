from django import forms

from apps.counterparties.models import Counterparty


class ReportForm(forms.Form):
    """Форма выбора параметров отчёта."""

    REPORT_CHOICES = [
        ("overdue_registry", "Реестр просроченной задолженности"),
        ("payment_calendar", "Платёжный календарь"),
        ("procurement_structure", "Структура закупок по поставщикам"),
        ("debt_by_terms", "Задолженность по срокам"),
        ("counterparty_card", "Карточка контрагента"),
    ]

    FORMAT_CHOICES = [
        ("excel", "Excel (.xlsx)"),
        ("pdf", "PDF"),
    ]

    report_type = forms.ChoiceField(
        label="Тип отчёта",
        choices=REPORT_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    output_format = forms.ChoiceField(
        label="Формат",
        choices=FORMAT_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    date_from = forms.DateField(
        label="Дата с",
        required=False,
        widget=forms.DateInput(attrs={
            "class": "form-control",
            "type": "date",
            "id": "id_date_from",
            "onchange": "updateDateTo()",
        }),
    )
    date_to = forms.DateField(
        label="Дата по",
        required=False,
        widget=forms.DateInput(attrs={
            "class": "form-control",
            "type": "date",
            "id": "id_date_to",
        }),
    )
    counterparty = forms.ModelChoiceField(
        label="Контрагент",
        queryset=Counterparty.objects.filter(is_active=True).order_by("name"),
        required=False,
        empty_label="— Все контрагенты —",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def clean(self):
        cleaned = super().clean()
        date_from = cleaned.get("date_from")
        date_to = cleaned.get("date_to")
        if date_from and date_to and date_to < date_from:
            raise forms.ValidationError(
                "Дата «по» не может быть раньше даты «с»."
            )
        return cleaned