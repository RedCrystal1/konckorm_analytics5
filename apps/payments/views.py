from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.accounts.decorators import manager_or_above_required

from .models import CashBalance, CashGapAlert
from .services import get_calendar_data


@manager_or_above_required
def payment_calendar_view(request):
    """Платёжный календарь с переключением день/неделя/месяц."""
    import calendar as cal_module

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

    # Добавляем is_today
    today = date.today()
    for day in calendar_data:
        day["is_today"] = day["date"] == today

    # Навигация
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    month_name = [
        "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
    ][month]

    # Фильтрация по режиму отображения
    if view_mode == "day":
        calendar_data = [d for d in calendar_data if d["date"] == today]
    elif view_mode == "week":
        from datetime import timedelta
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        calendar_data = [d for d in calendar_data if week_start <= d["date"] <= week_end]
    # else: month — показываем всё (по умолчанию)

    # Прогнозные остатки
    forecast_data = list(CashBalance.objects.order_by("date")[:30])

    # Кассовые разрывы
    cash_gap_alerts = CashGapAlert.objects.filter(is_acknowledged=False).order_by("date")[:10]

    return render(
        request,
        "payments/payment_calendar.html",
        {
            "calendar_data": calendar_data,
            "year": year,
            "month": month,
            "month_name": month_name,
            "view_mode": view_mode,
            "prev_month": prev_month,
            "prev_year": prev_year,
            "next_month": next_month,
            "next_year": next_year,
            "forecast_data": forecast_data,
            "cash_gap_alerts": cash_gap_alerts,
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
    """HTMX: детали дня в календаре."""
    from datetime import datetime

    from apps.registers.models import PlannedPayment

    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    payments = PlannedPayment.objects.filter(planned_date=day).select_related(
        "counterparty"
    )
    balance = CashBalance.objects.filter(date=day).first()

    return render(
        request,
        "payments/partials/_day_detail.html",
        {"day": day, "payments": payments, "balance": balance},
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
