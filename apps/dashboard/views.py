from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services import get_dashboard_kpi, get_overdue_top


@login_required
def dashboard_view(request):
    """Главная страница — дашборд."""
    from apps.analytics.services import get_kpi_history

    kpi = get_dashboard_kpi(user=request.user)
    overdue_top = get_overdue_top(limit=10, user=request.user)
    history = get_kpi_history(days=30)
    return render(
        request,
        "dashboard/index.html",
        {"kpi": kpi, "overdue_top": overdue_top, "history": history},
    )

# ── HTMX endpoints ──


@login_required
def htmx_kpi_cards(request):
    kpi = get_dashboard_kpi(user=request.user)
    return render(request, "dashboard/partials/_kpi_cards.html", {"kpi": kpi})


@login_required
def htmx_debt_chart(request):
    from apps.analytics.services import get_kpi_history

    days = int(request.GET.get("days", 30))
    history = get_kpi_history(days=days)
    return render(request, "dashboard/partials/_debt_chart.html", {"history": history})


@login_required
def htmx_overdue_table(request):
    overdue_top = get_overdue_top(limit=10, user=request.user)
    return render(
        request, "dashboard/partials/_overdue_table.html", {"overdue_top": overdue_top}
    )
