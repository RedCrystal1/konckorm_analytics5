from django import forms
from django.utils import timezone

from apps.counterparties.models import Contract, Counterparty
from apps.documents.models import GoodsReceipt

from .models import PaymentRequest


class PaymentRequestForm(forms.ModelForm):
    """Форма создания/редактирования заявки на оплату.

    Контрагент, договор и поступление-основание подгружаются динамически
    (например, через шаблон или JS) — в этой версии оставляем стандартные select.
    """

    class Meta:
        model = PaymentRequest
        fields = [
            "counterparty",
            "contract",
            "related_receipt",
            "amount",
            "planned_date",
            "priority",
            "purpose",
        ]
        widgets = {
            "counterparty": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "contract": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "related_receipt": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "amount": forms.NumberInput(attrs={
                "class": "form-control form-control-sm",
                "step": "0.01", "min": "0.01",
            }),
            "planned_date": forms.DateInput(attrs={
                "class": "form-control form-control-sm",
                "type": "date",
            }),
            "priority": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "purpose": forms.Textarea(attrs={
                "class": "form-control form-control-sm",
                "rows": 3,
                "placeholder": "Назначение платежа (будет передано в 1С)",
            }),
        }
        labels = {
            "counterparty": "Поставщик",
            "contract": "Договор",
            "related_receipt": "Поступление-основание (опционально)",
            "amount": "Сумма к оплате, ₽",
            "planned_date": "Планируемая дата платежа",
            "priority": "Приоритет",
            "purpose": "Назначение платежа",
        }

    def __init__(self, *args, **kwargs):
        # Если есть pre-selected counterparty, фильтруем договоры/поступления
        initial_cp = kwargs.get("initial", {}).get("counterparty")
        instance = kwargs.get("instance")
        if instance and instance.counterparty_id:
            initial_cp = instance.counterparty_id

        super().__init__(*args, **kwargs)
        self.fields["contract"].required = False
        self.fields["related_receipt"].required = False
        self.fields["contract"].empty_label = "— без договора —"
        self.fields["related_receipt"].empty_label = "— без поступления —"

        if initial_cp:
            self.fields["contract"].queryset = Contract.objects.filter(
                counterparty_id=initial_cp
            )
            self.fields["related_receipt"].queryset = GoodsReceipt.objects.filter(
                counterparty_id=initial_cp
            ).order_by("-date")[:50]

    def clean_planned_date(self):
        d = self.cleaned_data["planned_date"]
        if d < timezone.now().date():
            raise forms.ValidationError(
                "Планируемая дата не может быть в прошлом."
            )
        return d

    def clean_amount(self):
        a = self.cleaned_data["amount"]
        if a <= 0:
            raise forms.ValidationError("Сумма должна быть положительной.")
        return a


class PaymentRequestRejectForm(forms.Form):
    """Форма отклонения заявки (бухгалтер указывает причину)."""

    reason = forms.CharField(
        label="Причина отклонения",
        widget=forms.Textarea(attrs={
            "class": "form-control form-control-sm",
            "rows": 3,
            "placeholder": "Например: некорректная сумма, нет договора, дубль ранее отправленной заявки",
        }),
        max_length=2000,
        required=True,
    )

    def clean_reason(self):
        r = self.cleaned_data["reason"].strip()
        if len(r) < 5:
            raise forms.ValidationError("Причина должна быть содержательной (минимум 5 символов).")
        return r
