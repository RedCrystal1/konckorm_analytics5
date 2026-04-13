# from django import forms
#
# from .models import Discrepancy, ReconciliationAct
#
#
# class ReconciliationActForm(forms.ModelForm):
#     class Meta:
#         model = ReconciliationAct
#         fields = [
#             "counterparty",
#             "period_start",
#             "period_end",
#             "our_balance",
#             "their_balance",
#         ]
#         widgets = {
#             "counterparty": forms.Select(attrs={"class": "form-select"}),
#             "period_start": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
#             "period_end": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
#             "our_balance": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
#             "their_balance": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
#         }
#
#
# class DiscrepancyStatusForm(forms.ModelForm):
#     """Форма обновления статуса расхождения."""
#
#     class Meta:
#         model = Discrepancy
#         fields = ["status", "responsible", "resolution_comment"]
#         widgets = {
#             "status": forms.Select(attrs={"class": "form-select"}),
#             "responsible": forms.Select(attrs={"class": "form-select"}),
#             "resolution_comment": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
#         }
from django import forms
from apps.counterparties.models import Counterparty


class ReconciliationActForm(forms.Form):
    """Форма формирования акта сверки — только контрагент и период."""
    counterparty = forms.ModelChoiceField(
        label="Контрагент",
        queryset=Counterparty.objects.filter(is_active=True).order_by("name"),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    period_start = forms.DateField(
        label="Начало периода",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    period_end = forms.DateField(
        label="Конец периода",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("period_start")
        end = cleaned.get("period_end")
        if start and end and end < start:
            raise forms.ValidationError("Конец периода не может быть раньше начала.")
        return cleaned


class DiscrepancyStatusForm(forms.Form):
    """Форма изменения статуса расхождения."""
    STATUS_CHOICES = [
        ("open", "Открыто"),
        ("in_progress", "В работе"),
        ("resolved", "Закрыто"),
    ]
    status = forms.ChoiceField(
        label="Статус",
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    resolution_comment = forms.CharField(
        label="Комментарий",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )