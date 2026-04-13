from django.db.models import Q, Sum
from django.utils import timezone

from .models import Counterparty, CounterpartyHistorySnapshot


def find_duplicates(inn=None, name=None):
    """Поиск дублей по ИНН или наименованию."""
    results = []

    if inn:
        exact = Counterparty.objects.filter(inn=inn)
        for cp in exact:
            results.append({"counterparty": cp, "match_field": "inn", "confidence": 1.0})

    if name:
        similar = Counterparty.objects.filter(
            Q(name__icontains=name) | Q(full_name__icontains=name)
        )
        if inn:
            similar = similar.exclude(inn=inn)
        for cp in similar:
            results.append({"counterparty": cp, "match_field": "name", "confidence": 0.7})

    return results


def create_history_snapshot(counterparty, user=None):
    """Создание снимка текущего состояния контрагента."""
    data = {
        "name": counterparty.name,
        "full_name": counterparty.full_name,
        "inn": counterparty.inn,
        "kpp": counterparty.kpp,
        "legal_address": counterparty.legal_address,
        "actual_address": counterparty.actual_address,
        "phone": counterparty.phone,
        "email": counterparty.email,
        "contact_person": counterparty.contact_person,
        "is_key_supplier": counterparty.is_key_supplier,
        "is_active": counterparty.is_active,
    }
    snapshot, created = CounterpartyHistorySnapshot.objects.update_or_create(
        counterparty=counterparty,
        snapshot_date=timezone.now().date(),
        defaults={
            "data": data,
            "changed_by": user,
        },
    )
    return snapshot


def get_counterparty_debt_summary(counterparty):
    """Сводка задолженности по контрагенту."""
    from apps.documents.models import GoodsReceipt

    receipts = GoodsReceipt.objects.filter(counterparty=counterparty, is_paid=False)
    total = receipts.aggregate(
        total_amount=Sum("amount"),
        total_paid=Sum("paid_amount"),
    )
    total_amount = total["total_amount"] or 0
    total_paid = total["total_paid"] or 0

    overdue_receipts = [r for r in receipts if r.overdue_days > 0]
    overdue_amount = sum(r.outstanding_amount for r in overdue_receipts)

    return {
        "total_debt": total_amount - total_paid,
        "overdue_amount": overdue_amount,
        "overdue_count": len(overdue_receipts),
        "unpaid_count": receipts.count(),
    }
