import logging
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.documents.models import GoodsReceipt

from .models import DebtByTerms, PlannedPayment, ProcurementVolume

logger = logging.getLogger("apps.registers")


def update_debt_statuses():
    """Пересчёт статусов и дней просрочки для всех незакрытых записей."""
    today = timezone.now().date()

    unpaid_receipts = GoodsReceipt.objects.filter(is_paid=False).select_related(
        "counterparty", "contract", "counterparty__responsible_manager"
    )

    updated = 0
    for receipt in unpaid_receipts:
        outstanding = receipt.outstanding_amount
        if outstanding <= 0:
            continue

        overdue_days = max(0, (today - receipt.payment_due_date).days)

        if overdue_days == 0:
            status = DebtByTerms.DebtStatus.CURRENT
            overdue_amount = Decimal("0")
        elif overdue_days <= 30:
            status = DebtByTerms.DebtStatus.OVERDUE_30
            overdue_amount = outstanding
        elif overdue_days <= 60:
            status = DebtByTerms.DebtStatus.OVERDUE_60
            overdue_amount = outstanding
        elif overdue_days <= 90:
            status = DebtByTerms.DebtStatus.OVERDUE_90
            overdue_amount = outstanding
        else:
            status = DebtByTerms.DebtStatus.OVERDUE_90_PLUS
            overdue_amount = outstanding

        DebtByTerms.objects.update_or_create(
            source_document=receipt,
            defaults={
                "counterparty": receipt.counterparty,
                "contract": receipt.contract,
                "planned_payment_date": receipt.payment_due_date,
                "status": status,
                "responsible_manager": getattr(
                    receipt.counterparty, "responsible_manager", None
                ),
                "amount_rub": outstanding,
                "overdue_amount": overdue_amount,
                "overdue_days": overdue_days,
            },
        )
        updated += 1

    # Удаляем записи для оплаченных документов
    paid_ids = GoodsReceipt.objects.filter(is_paid=True).values_list("id", flat=True)
    DebtByTerms.objects.filter(source_document_id__in=paid_ids).delete()

    logger.info("Обновлено записей регистра задолженности: %d", updated)
    return updated


def update_planned_payments():
    """Обновление статусов плановых платежей."""
    today = timezone.now().date()

    # Просроченные
    PlannedPayment.objects.filter(
        status=PlannedPayment.PaymentStatus.PENDING,
        planned_date__lt=today,
    ).update(status=PlannedPayment.PaymentStatus.OVERDUE)

    # Вычисляем отклонение для исполненных
    completed = PlannedPayment.objects.filter(
        status=PlannedPayment.PaymentStatus.COMPLETED,
        actual_date__isnull=False,
        deviation_days=0,
    )
    for pp in completed:
        pp.deviation_days = (pp.actual_date - pp.planned_date).days
        pp.save(update_fields=["deviation_days"])


def calculate_procurement_volumes(period_start, period_end, period_type="month"):
    """Расчёт объёмов закупок за период."""
    from apps.counterparties.models import Counterparty

    receipts = GoodsReceipt.objects.filter(
        date__gte=period_start,
        date__lte=period_end,
    )

    total_volume = receipts.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    counterparties = (
        receipts.values("counterparty")
        .annotate(volume=Sum("amount"))
        .order_by("-volume")
    )

    created = 0
    for entry in counterparties:
        cp_id = entry["counterparty"]
        volume = entry["volume"]
        share = (volume / total_volume * 100) if total_volume > 0 else Decimal("0")

        ProcurementVolume.objects.update_or_create(
            counterparty_id=cp_id,
            period_start=period_start,
            period_end=period_end,
            period_type=period_type,
            defaults={
                "volume_rub": volume,
                "share_percent": share,
            },
        )
        created += 1

    logger.info(
        "Рассчитаны объёмы закупок за %s — %s: %d записей",
        period_start,
        period_end,
        created,
    )
    return created
