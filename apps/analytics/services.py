import logging

from django.utils import timezone

from .calculators import (
    calculate_avg_deviation_days,
    calculate_avg_payment_days,
    calculate_cash_gap_probability,
    calculate_forecast_cash_need,
    calculate_key_supplier_share,
    calculate_overdue_debt,
    calculate_overdue_ratio,
    calculate_payment_ratio,
    calculate_total_debt,
    calculate_turnover_days,
)
from .models import AnalyticsSnapshot

logger = logging.getLogger("apps.analytics")


def recalculate_all_kpi():
    """Полный пересчёт всех KPI и сохранение снимка."""
    today = timezone.now().date()

    total_debt = calculate_total_debt()
    overdue_debt = calculate_overdue_debt()
    overdue_ratio = calculate_overdue_ratio(total_debt, overdue_debt)
    turnover_days = calculate_turnover_days()
    payment_ratio = calculate_payment_ratio()
    avg_payment_days = calculate_avg_payment_days()
    avg_deviation_days = calculate_avg_deviation_days()
    key_supplier_share = calculate_key_supplier_share()
    forecast_week = calculate_forecast_cash_need(days=7)
    forecast_month = calculate_forecast_cash_need(days=30)
    cash_gap_prob = calculate_cash_gap_probability()

    snapshot, created = AnalyticsSnapshot.objects.update_or_create(
        date=today,
        defaults={
            "total_debt": total_debt,
            "overdue_debt": overdue_debt,
            "overdue_ratio": overdue_ratio,
            "turnover_days": turnover_days,
            "payment_ratio": payment_ratio,
            "avg_payment_days": avg_payment_days,
            "avg_deviation_days": avg_deviation_days,
            "key_supplier_share": key_supplier_share,
            "forecast_cash_need_week": forecast_week,
            "forecast_cash_need_month": forecast_month,
            "cash_gap_probability": cash_gap_prob,
        },
    )

    action = "Создан" if created else "Обновлён"
    logger.info("%s аналитический снимок за %s", action, today)

    return snapshot


def get_latest_kpi():
    """Получение последнего снимка KPI."""
    try:
        return AnalyticsSnapshot.objects.latest()
    except AnalyticsSnapshot.DoesNotExist:
        return None


def get_kpi_history(days=30):
    """История KPI за последние N дней."""
    from datetime import timedelta

    date_from = timezone.now().date() - timedelta(days=days)
    return AnalyticsSnapshot.objects.filter(date__gte=date_from).order_by("date")
