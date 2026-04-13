from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.utils import timezone


def get_dashboard_kpi(user=None):
    """Получение KPI для дашборда."""
    from apps.analytics.services import get_latest_kpi
    from apps.registers.models import DebtByTerms, PlannedPayment

    kpi = get_latest_kpi()

    # Если нет снимка, рассчитываем на лету
    if not kpi:
        from apps.analytics.calculators import (
            calculate_key_supplier_share,
            calculate_overdue_debt,
            calculate_overdue_ratio,
            calculate_total_debt,
            calculate_turnover_days,
        )

        total_debt = calculate_total_debt()
        overdue_debt = calculate_overdue_debt()
        overdue_ratio = calculate_overdue_ratio(total_debt, overdue_debt)
        turnover_days = calculate_turnover_days()
        key_supplier_share = calculate_key_supplier_share()
    else:
        total_debt = kpi.total_debt
        overdue_debt = kpi.overdue_debt
        overdue_ratio = kpi.overdue_ratio
        turnover_days = kpi.turnover_days
        key_supplier_share = kpi.key_supplier_share

    # Количество просроченных платежей
    overdue_count = DebtByTerms.objects.exclude(
        status=DebtByTerms.DebtStatus.CURRENT
    ).count()

    # Предстоящие платежи (ближайшие 7 дней)
    today = timezone.now().date()
    from datetime import timedelta

    upcoming = PlannedPayment.objects.filter(
        status=PlannedPayment.PaymentStatus.PENDING,
        planned_date__gte=today,
        planned_date__lte=today + timedelta(days=7),
    ).aggregate(count=Count("id"), total=Sum("amount"))

    # Определяем цвет для KPI
    thresholds = getattr(settings, "KPI_THRESHOLDS", {})
    overdue_th = thresholds.get("overdue_ratio", {})
    if overdue_ratio < Decimal(str(overdue_th.get("green", 5) * 100)):
        overdue_color = "success"
    elif overdue_ratio < Decimal(str(overdue_th.get("yellow", 15) * 100)):
        overdue_color = "warning"
    else:
        overdue_color = "danger"

    # Цвет оборачиваемости
    turnover_th = thresholds.get("turnover_days", {})
    if turnover_days < Decimal(str(turnover_th.get("green", 30))):
        turnover_color = "success"
    elif turnover_days < Decimal(str(turnover_th.get("yellow", 60))):
        turnover_color = "warning"
    else:
        turnover_color = "danger"

    return {
        "total_debt": total_debt,
        "overdue_debt": overdue_debt,
        "overdue_ratio": overdue_ratio,
        "overdue_count": overdue_count,
        "overdue_color": overdue_color,
        "turnover_days": turnover_days,
        "turnover_color": turnover_color,
        "key_supplier_share": key_supplier_share,
        "upcoming_count": upcoming["count"] or 0,
        "upcoming_total": upcoming["total"] or Decimal("0"),
        "kpi_snapshot": kpi,
    }


def get_overdue_top(limit=10, user=None):
    """Топ просроченных платежей для таблицы на дашборде."""
    from apps.registers.models import DebtByTerms

    qs = DebtByTerms.objects.exclude(
        status=DebtByTerms.DebtStatus.CURRENT
    ).select_related("counterparty", "source_document").order_by("-overdue_days")

    if user and user.is_procurement:
        qs = qs.filter(
            Q(responsible_manager=user)
            | Q(counterparty__user_access__user=user)
        ).distinct()

    return qs[:limit]
