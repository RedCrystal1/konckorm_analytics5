import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from .models import CashBalance, CashGapAlert

logger = logging.getLogger("apps.payments")


def forecast_cash_balances(
    opening_balance=Decimal("0"),
    horizon_days=None,
):
    """Прогнозирование остатков ДС на горизонт.

    Строит CashBalance на каждый день, выявляет кассовые разрывы.
    """
    from apps.registers.models import PlannedPayment

    if horizon_days is None:
        horizon_days = getattr(
            settings, "PAYMENT_CALENDAR_DEFAULT_HORIZON", 30
        )

    today = timezone.now().date()
    balance = opening_balance
    gaps = []

    for day_offset in range(horizon_days):
        current_date = today + timedelta(days=day_offset)

        # Исходящие платежи на этот день
        outflow = (
            PlannedPayment.objects.filter(
                planned_date=current_date,
                status__in=["pending", "overdue"],
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )

        # TODO: входящие платежи (из плана поступлений)
        inflow = Decimal("0")

        closing = balance + inflow - outflow
        is_gap = closing < 0

        CashBalance.objects.update_or_create(
            date=current_date,
            defaults={
                "opening_balance": balance,
                "total_inflow": inflow,
                "total_outflow": outflow,
                "closing_balance": closing,
                "is_cash_gap": is_gap,
            },
        )

        if is_gap:
            gaps.append(
                {
                    "date": current_date,
                    "deficit": abs(closing),
                }
            )

        balance = closing

    return gaps


def create_cash_gap_alerts(gaps):
    """Создание предупреждений о кассовых разрывах."""
    from apps.registers.models import PlannedPayment

    created = 0
    for gap in gaps:
        alert, is_new = CashGapAlert.objects.get_or_create(
            date=gap["date"],
            defaults={"deficit_amount": gap["deficit"]},
        )
        if is_new:
            # Привязываем платежи, вызывающие разрыв
            payments = PlannedPayment.objects.filter(
                planned_date=gap["date"],
                status__in=["pending", "overdue"],
            )
            alert.contributing_payments.set(payments)
            created += 1
        else:
            alert.deficit_amount = gap["deficit"]
            alert.save(update_fields=["deficit_amount"])

    logger.info("Создано предупреждений о кассовых разрывах: %d", created)
    return created


def get_calendar_data(year, month):
    """Данные для календарной сетки."""
    import calendar
    from datetime import date

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.itermonthdates(year, month)

    # Получаем все плановые платежи за месяц
    from apps.registers.models import PlannedPayment

    month_start = date(year, month, 1)
    if month == 12:
        month_end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(year, month + 1, 1) - timedelta(days=1)

    payments = PlannedPayment.objects.filter(
        planned_date__gte=month_start,
        planned_date__lte=month_end,
    ).select_related("counterparty")

    payments_by_date = {}
    for p in payments:
        payments_by_date.setdefault(p.planned_date, []).append(p)

    balances = CashBalance.objects.filter(
        date__gte=month_start,
        date__lte=month_end,
    )
    balances_by_date = {b.date: b for b in balances}

    days_data = []
    for d in month_days:
        days_data.append(
            {
                "date": d,
                "in_month": d.month == month,
                "payments": payments_by_date.get(d, []),
                "balance": balances_by_date.get(d),
                "is_cash_gap": balances_by_date.get(d, None)
                and balances_by_date[d].is_cash_gap,
            }
        )

    return days_data
