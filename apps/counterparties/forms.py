from django import forms

from .models import Contract, Counterparty


class CounterpartyForm(forms.ModelForm):
    class Meta:
        model = Counterparty
        fields = [
            "code_1c",
            "name",
            "full_name",
            "inn",
            "kpp",
            "legal_address",
            "actual_address",
            "phone",
            "email",
            "contact_person",
            "is_key_supplier",
            "is_active",
            "responsible_manager",
            "notes",
        ]
        widgets = {
            "code_1c": forms.TextInput(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "inn": forms.TextInput(attrs={"class": "form-control", "maxlength": 12}),
            "kpp": forms.TextInput(attrs={"class": "form-control", "maxlength": 9}),
            "legal_address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "actual_address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "contact_person": forms.TextInput(attrs={"class": "form-control"}),
            "is_key_supplier": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "responsible_manager": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean_inn(self):
        inn = self.cleaned_data["inn"]
        if inn and len(inn) not in (10, 12):
            raise forms.ValidationError("ИНН должен содержать 10 или 12 цифр.")
        if inn and not inn.isdigit():
            raise forms.ValidationError("ИНН должен содержать только цифры.")
        return inn


class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = [
            "code_1c",
            "counterparty",
            "number",
            "name",
            "date",
            "kind",
            "currency",
            "payment_term_type",
            "payment_days",
            "credit_limit",
            "penalty_rate",
            "valid_from",
            "valid_to",
            "is_active",
        ]
        widgets = {
            "code_1c": forms.TextInput(attrs={"class": "form-control"}),
            "counterparty": forms.Select(attrs={"class": "form-select"}),
            "number": forms.TextInput(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "kind": forms.Select(attrs={"class": "form-select"}),
            "currency": forms.Select(attrs={"class": "form-select"}),
            "payment_term_type": forms.Select(attrs={"class": "form-select"}),
            "payment_days": forms.NumberInput(attrs={"class": "form-control"}),
            "credit_limit": forms.NumberInput(attrs={"class": "form-control"}),
            "penalty_rate": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "valid_from": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "valid_to": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
