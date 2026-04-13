from django import forms

from .models import GoodsReceipt, Invoice, PaymentOrder


class GoodsReceiptForm(forms.ModelForm):
    class Meta:
        model = GoodsReceipt
        fields = [
            "number",
            "date",
            "counterparty",
            "contract",
            "amount",
            "currency",
            "payment_due_date",
            "notes",
        ]
        widgets = {
            "number": forms.TextInput(attrs={"class": "form-control"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "counterparty": forms.Select(attrs={"class": "form-select"}),
            "contract": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "currency": forms.TextInput(attrs={"class": "form-control"}),
            "payment_due_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class PaymentOrderForm(forms.ModelForm):
    class Meta:
        model = PaymentOrder
        fields = [
            "number",
            "date",
            "counterparty",
            "contract",
            "amount",
            "payment_purpose",
            "related_receipt",
            "notes",
        ]
        widgets = {
            "number": forms.TextInput(attrs={"class": "form-control"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "counterparty": forms.Select(attrs={"class": "form-select"}),
            "contract": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "payment_purpose": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "related_receipt": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = [
            "number",
            "date",
            "counterparty",
            "contract",
            "direction",
            "amount",
            "payment_due_date",
            "notes",
        ]
        widgets = {
            "number": forms.TextInput(attrs={"class": "form-control"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "counterparty": forms.Select(attrs={"class": "form-select"}),
            "contract": forms.Select(attrs={"class": "form-select"}),
            "direction": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "payment_due_date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }
