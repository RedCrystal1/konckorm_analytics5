import logging
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, F, Sum
from django.utils import timezone

logger = logging.getLogger("apps.analytics")


def calculate_total_debt():
    """Общая сумма кредиторской задолженности."""
    from apps.documents.models import GoodsReceipt

    result = GoodsReceipt.objects.filter(is_paid=False).aggregate(
        total=Sum(F("amount") - F("paid_amount"))
    )
    return result["total"] or Decimal("0")


def calculate_overdue_debt():
    """Сумма просроченной КЗ."""
    from apps.registers.models import DebtByTerms

    result = DebtByTerms.objects.exclude(
        status=DebtByTerms.DebtStatus.CURRENT
    ).aggregate(total=Sum("overdue_amount"))
    return result["total"] or Decimal("0")


def calculate_overdue_ratio(total_debt, overdue_debt):
    """Доля просроченной КЗ в процентах."""
    if total_debt == 0:
        return Decimal("0")
    return (overdue_debt / total_debt * 100).quantize(Decimal("0.01"))


def calculate_turnover_days():
    """Оборачиваемость КЗ в днях.

    Формула: (Средняя КЗ / Оборот по кредиту 60) * кол-во дней в периоде
    Упрощённый расчёт за последние 30 дней.
    """
    from apps.documents.models import GoodsReceipt, PaymentOrder

    period_days = 30
    date_from = timezone.now().date() - timedelta(days=period_days)

    avg_debt = calculate_total_debt()
    turnover = (
        PaymentOrder.objects.filter(date__gte=date_from).aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0")
    )

    if turnover == 0:
        return Decimal("0")

    return (avg_debt / turnover * period_days).quantize(Decimal("0.1"))


def calculate_payment_ratio():
    """Коэффициент погашения = Оплачено / Начислено за период."""
    from apps.documents.models import GoodsReceipt, PaymentOrder

    period_days = 30
    date_from = timezone.now().date() - timedelta(days=period_days)

    accrued = (
        GoodsReceipt.objects.filter(date__gte=date_from).aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0")
    )
    paid = (
        PaymentOrder.objects.filter(date__gte=date_from).aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0")
    )

    if accrued == 0:
        return Decimal("0")

    return (paid / accrued).quantize(Decimal("0.001"))


def calculate_avg_payment_days():
    """Средний фактический срок оплаты (дни)."""
    from apps.registers.models import PlannedPayment

    completed = PlannedPayment.objects.filter(
        status=PlannedPayment.PaymentStatus.COMPLETED,
        actual_date__isnull=False,
    )
    if not completed.exists():
        return Decimal("0")

    avg = completed.aggregate(
        avg_days=Avg(F("actual_date") - F("source_document__date"))
    )
    val = avg.get("avg_days")
    if val is None:
        return Decimal("0")
    return Decimal(str(val.days if hasattr(val, "days") else val)).quantize(
        Decimal("0.1")
    )


def calculate_avg_deviation_days():
    """Среднее отклонение от договорных сроков."""
    from apps.registers.models import PlannedPayment

    completed = PlannedPayment.objects.filter(
        status=PlannedPayment.PaymentStatus.COMPLETED,
    ).exclude(deviation_days=0)

    if not completed.exists():
        return Decimal("0")

    avg = completed.aggregate(avg_dev=Avg("deviation_days"))
    return Decimal(str(avg["avg_dev"] or 0)).quantize(Decimal("0.1"))


def calculate_key_supplier_share():
    """Доля ключевых поставщиков в общем объёме закупок (%)."""
    from apps.documents.models import GoodsReceipt

    period_days = 90
    date_from = timezone.now().date() - timedelta(days=period_days)

    total = (
        GoodsReceipt.objects.filter(date__gte=date_from).aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0")
    )
    key = (
        GoodsReceipt.objects.filter(
            date__gte=date_from, counterparty__is_key_supplier=True
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    if total == 0:
        return Decimal("0")

    return (key / total * 100).quantize(Decimal("0.01"))


def calculate_forecast_cash_need(days=7):
    """Прогноз потребности в денежных средствах на N дней."""
    from apps.registers.models import PlannedPayment

    today = timezone.now().date()
    horizon = today + timedelta(days=days)

    result = PlannedPayment.objects.filter(
        status=PlannedPayment.PaymentStatus.PENDING,
        planned_date__gte=today,
        planned_date__lte=horizon,
    ).aggregate(total=Sum("amount"))

    return result["total"] or Decimal("0")


def calculate_cash_gap_probability():
    """Вероятность кассового разрыва в ближайшие 30 дней.

    Эвристика: доля дней с отрицательным прогнозным остатком.
    """
    from apps.payments.models import CashBalance

    today = timezone.now().date()
    horizon = today + timedelta(days=30)

    balances = CashBalance.objects.filter(date__gte=today, date__lte=horizon)
    total_days = balances.count()

    if total_days == 0:
        return Decimal("0")

    gap_days = balances.filter(is_cash_gap=True).count()
    return (Decimal(gap_days) / Decimal(total_days) * 100).quantize(Decimal("0.1"))
