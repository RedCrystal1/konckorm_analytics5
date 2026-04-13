from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("", views.analytics_dashboard_view, name="dashboard"),
    path("procurement/", views.procurement_structure_view, name="procurement"),
    # JSON API для графиков
    path("api/kpi-history/", views.api_kpi_history, name="api_kpi_history"),
    path("api/procurement-data/", views.api_procurement_data, name="api_procurement_data"),
]
