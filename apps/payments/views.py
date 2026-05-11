from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import render

from apps.accounts.decorators import manager_or_above_required

from .models import CashBalance, CashGapAlert
from .services import get_calendar_data


@manager_or_above_required
def payment_calendar_view(request):
    """Платёжный календарь с режимами вида: month / week / day / list / forecast."""
    from apps.registers.models import PlannedPayment

    year = int(request.GET.get("year", date.today().year))
    month = int(request.GET.get("month", date.today().month))
    view_mode = request.GET.get("view", "month")

    # Корректируем выход за границы
    if month < 1:
        month = 12
        year -= 1
    elif month > 12:
        month = 1
        year += 1

    calendar_data = get_calendar_data(year, month)

    # Добавляем is_today + cell_status (для цвета ячейки в календаре)
    today = date.today()
    for day in calendar_data:
        day["is_today"] = day["date"] == today

        # Определяем статус ячейки с приоритетом:
        # gap > overdue > paid > pending > пусто.
        # Просрочкой считаем платёж со status='overdue' ИЛИ
        # с просроченной плановой датой при незавершённом статусе
        # (на случай если cron-обновление статусов ещё не отработало).
        if day.get("is_cash_gap"):
            day["cell_status"] = "gap"
        elif not day["payments"]:
            day["cell_status"] = ""
        else:
            has_overdue = False
            all_paid = True
            for p in day["payments"]:
                is_overdue = (
                    p.status == "overdue"
                    or (p.planned_date < today and p.status not in ("completed", "cancelled"))
                )
                if is_overdue:
                    has_overdue = True
                if p.status != "completed":
                    all_paid = False

            if has_overdue:
                day["cell_status"] = "overdue"
            elif all_paid:
                day["cell_status"] = "paid"
            else:
                day["cell_status"] = "pending"

    # Навигация
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    month_name = [
        "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ][month]

    # Сводка для подзаголовка (подсчитываем по всему месяцу)
    month_summary = {
        "total": Decimal("0"),
        "paid": Decimal("0"),
        "count": 0,
    }
    payments_by_day_for_list = {}  # для режима list
    for day in calendar_data:
        if not day["in_month"]:
            continue
        for p in day["payments"]:
            month_summary["total"] += p.amount
            month_summary["count"] += 1
            if p.status == "completed":
                month_summary["paid"] += p.amount
        if day["payments"] and day["in_month"]:
            payments_by_day_for_list[day["date"]] = day["payments"]

    # Прогнозные остатки (всегда считаем для всех режимов — нужны на разрывы)
    forecast_data = list(CashBalance.objects.order_by("date")[:30])

    # Минимум/максимум прогноза для режима forecast
    forecast_extremes = None
    if forecast_data:
        min_balance = min(forecast_data, key=lambda b: b.closing_balance)
        max_balance = max(forecast_data, key=lambda b: b.closing_balance)
        forecast_extremes = {"min": min_balance, "max": max_balance}

    # Кассовые разрывы (только неподтверждённые)
    cash_gap_alerts = list(
        CashGapAlert.objects.filter(is_acknowledged=False).order_by("date")[:10]
    )

    # Платёжная дисциплина — за прошлый месяц
    last_month_total = PlannedPayment.objects.filter(
        planned_date__year=year, planned_date__month=month,
    ).count()
    last_month_paid = PlannedPayment.objects.filter(
        planned_date__year=year, planned_date__month=month, status="completed",
    ).count()
    last_month_overdue = PlannedPayment.objects.filter(
        planned_date__year=year, planned_date__month=month, status="overdue",
    ).count()
    discipline = {
        "total": last_month_total,
        "paid": last_month_paid,
        "overdue": last_month_overdue,
        "rate": int(last_month_paid / last_month_total * 100) if last_month_total else 0,
    }

    # Фильтрация по режиму отображения (не убираем оригинал — нужен для список/прогноз)
    filtered_calendar = calendar_data
    if view_mode == "day":
        filtered_calendar = [d for d in calendar_data if d["date"] == today]
    elif view_mode == "week":
        from datetime import timedelta
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        filtered_calendar = [
            d for d in calendar_data if week_start <= d["date"] <= week_end
        ]

    return render(
        request,
        "payments/payment_calendar.html",
        {
            "calendar_data": filtered_calendar,
            "calendar_full": calendar_data,  # полные данные месяца (для список/прогноз)
            "payments_by_day": sorted(payments_by_day_for_list.items()),
            "year": year,
            "month": month,
            "month_name": month_name,
            "view_mode": view_mode,
            "prev_month": prev_month,
            "prev_year": prev_year,
            "next_month": next_month,
            "next_year": next_year,
            "forecast_data": forecast_data,
            "forecast_extremes": forecast_extremes,
            "cash_gap_alerts": cash_gap_alerts,
            "month_summary": month_summary,
            "discipline": discipline,
            "today": today,
        },
    )


@manager_or_above_required
def cash_gap_alert_list_view(request):
    """Список предупреждений о кассовых разрывах."""
    alerts = CashGapAlert.objects.all()
    show_acknowledged = request.GET.get("show_acknowledged")
    if not show_acknowledged:
        alerts = alerts.filter(is_acknowledged=False)
    return render(
        request,
        "payments/cash_gap_alerts.html",
        {"alerts": alerts},
    )


# ── HTMX ──


@manager_or_above_required
def htmx_calendar_grid(request):
    year = int(request.GET.get("year", date.today().year))
    month = int(request.GET.get("month", date.today().month))
    calendar_data = get_calendar_data(year, month)
    return render(
        request,
        "payments/partials/_calendar_grid.html",
        {"calendar_data": calendar_data, "year": year, "month": month},
    )


@manager_or_above_required
def htmx_day_detail(request, date_str):
    """HTMX: детали дня в календаре — попап со списком платежей."""
    from datetime import datetime, date as date_cls

    from apps.registers.models import PlannedPayment

    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    payments = (
        PlannedPayment.objects
        .filter(planned_date=day)
        .select_related("counterparty", "source_document", "contract")
        .order_by("-amount")
    )
    balance = CashBalance.objects.filter(date=day).first()
    today = date_cls.today()

    # Считаем статус каждого платежа для подсветки
    payments_data = []
    total_amount = Decimal("0")
    for p in payments:
        is_overdue = (
            p.status == "overdue"
            or (p.planned_date < today and p.status not in ("completed", "cancelled"))
        )
        payments_data.append({
            "obj": p,
            "is_overdue": is_overdue,
        })
        total_amount += p.amount

    return render(
        request,
        "payments/partials/_day_popup.html",
        {
            "day": day,
            "payments_data": payments_data,
            "balance": balance,
            "total_amount": total_amount,
            "is_today": day == today,
            "is_past": day < today,
            "is_cash_gap": balance.is_cash_gap if balance else False,
        },
    )


@manager_or_above_required
def htmx_forecast_chart(request):
    """HTMX: график прогноза остатков."""
    balances = CashBalance.objects.order_by("date")[:30]
    return render(
        request,
        "payments/partials/_forecast_chart.html",
        {"balances": balances},
    )
