from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_view, name="index"),
    # HTMX
    path("htmx/kpi-cards/", views.htmx_kpi_cards, name="htmx_kpi_cards"),
    path("htmx/debt-chart/", views.htmx_debt_chart, name="htmx_debt_chart"),
    path("htmx/overdue-table/", views.htmx_overdue_table, name="htmx_overdue_table"),
]
