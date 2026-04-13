from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from apps.accounts.decorators import manager_or_above_required

from .services import get_kpi_history, get_latest_kpi


@manager_or_above_required
def analytics_dashboard_view(request):
    """Аналитический дашборд с KPI."""
    kpi = get_latest_kpi()
    history = get_kpi_history(days=30)
    return render(
        request,
        "analytics/analytics_dashboard.html",
        {"kpi": kpi, "history": history},
    )


@manager_or_above_required
def procurement_structure_view(request):
    """Структура закупок с детализацией по виду."""
    from django.db.models import Sum

    from apps.registers.models import ProcurementVolume

    volumes = ProcurementVolume.objects.select_related("counterparty").order_by(
        "-volume_rub"
    )

    # Фильтр по виду закупок
    kind_filter = request.GET.get("kind")
    if kind_filter:
        volumes = volumes.filter(procurement_kind=kind_filter)

    # Группировка по видам для диаграммы
    by_kind = (
        ProcurementVolume.objects.values("procurement_kind")
        .annotate(total=Sum("volume_rub"))
        .order_by("-total")
    )
    kind_labels = {"raw": "Сырьё", "material": "Материалы", "service": "Услуги"}
    kind_chart = [
        {"kind": kind_labels.get(r["procurement_kind"], r["procurement_kind"]), "total": float(r["total"])}
        for r in by_kind
    ]

    # Топ-20 поставщиков
    top_volumes = volumes[:20]

    return render(
        request,
        "analytics/procurement_structure.html",
        {
            "volumes": top_volumes,
            "kind_chart": kind_chart,
            "kind_filter": kind_filter,
        },
    )


@manager_or_above_required
def api_kpi_history(request):
    """JSON API: история KPI для графиков Chart.js."""
    days = int(request.GET.get("days", 30))
    history = get_kpi_history(days=days)
    data = {
        "labels": [s.date.strftime("%d.%m") for s in history],
        "total_debt": [float(s.total_debt) for s in history],
        "overdue_debt": [float(s.overdue_debt) for s in history],
        "overdue_ratio": [float(s.overdue_ratio) for s in history],
        "turnover_days": [float(s.turnover_days) for s in history],
    }
    return JsonResponse(data)


@manager_or_above_required
def api_procurement_data(request):
    """JSON API: данные по структуре закупок для графиков."""
    from apps.registers.models import ProcurementVolume

    volumes = ProcurementVolume.objects.select_related("counterparty").order_by(
        "-volume_rub"
    )[:10]
    data = {
        "labels": [v.counterparty.name for v in volumes],
        "values": [float(v.volume_rub) for v in volumes],
        "shares": [float(v.share_percent) for v in volumes],
    }
    return JsonResponse(data)
