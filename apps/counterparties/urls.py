from django.urls import path

from . import views

app_name = "counterparties"

urlpatterns = [
    path("", views.counterparty_list_view, name="list"),
    path("<int:pk>/", views.counterparty_detail_view, name="detail"),
    path("create/", views.counterparty_create_view, name="create"),
    path("<int:pk>/edit/", views.counterparty_update_view, name="edit"),
    path("contracts/", views.contract_list_view, name="contract_list"),
    path("contracts/<int:pk>/", views.contract_detail_view, name="contract_detail"),
    # HTMX
    path("htmx/table/", views.htmx_counterparty_table, name="htmx_table"),
    path("htmx/<int:pk>/debt-history/", views.htmx_debt_history, name="htmx_debt_history"),
    path("htmx/<int:pk>/debt-chart/", views.htmx_counterparty_chart, name="htmx_chart"),
]
