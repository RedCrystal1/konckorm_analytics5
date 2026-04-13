from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("calendar/", views.payment_calendar_view, name="calendar"),
    path("alerts/", views.cash_gap_alert_list_view, name="alerts"),
    # HTMX
    path("htmx/calendar-grid/", views.htmx_calendar_grid, name="htmx_calendar_grid"),
    path("htmx/day-detail/<str:date_str>/", views.htmx_day_detail, name="htmx_day_detail"),
    path("htmx/forecast-chart/", views.htmx_forecast_chart, name="htmx_forecast_chart"),
]
