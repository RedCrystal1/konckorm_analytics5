from django.urls import path

from . import payment_request_views as pr_views
from . import views

app_name = "payments"

urlpatterns = [
    # ── Календарь и алёрты по кассовым разрывам ──
    path("calendar/", views.payment_calendar_view, name="calendar"),
    path("alerts/", views.cash_gap_alert_list_view, name="alerts"),

    # HTMX для календаря/прогноза
    path("htmx/calendar-grid/", views.htmx_calendar_grid, name="htmx_calendar_grid"),
    path("htmx/day-detail/<str:date_str>/", views.htmx_day_detail, name="htmx_day_detail"),
    path("htmx/forecast-chart/", views.htmx_forecast_chart, name="htmx_forecast_chart"),

    # ── Заявки на оплату (workflow Менеджер → Бухгалтер → 1С) ──
    path("requests/", pr_views.payment_request_list_view, name="request_list"),
    path("requests/new/", pr_views.payment_request_create_view, name="request_create"),
    path("requests/<int:pk>/", pr_views.payment_request_detail_view, name="request_detail"),
    path("requests/<int:pk>/edit/", pr_views.payment_request_update_view, name="request_update"),

    # POST-эндпоинты действий workflow
    path("requests/<int:pk>/submit/", pr_views.payment_request_submit_view, name="request_submit"),
    path("requests/<int:pk>/approve/", pr_views.payment_request_approve_view, name="request_approve"),
    path("requests/<int:pk>/reject/", pr_views.payment_request_reject_view, name="request_reject"),
    path("requests/<int:pk>/send-to-1c/", pr_views.payment_request_send_to_1c_view, name="request_send_to_1c"),
    path("requests/<int:pk>/cancel/", pr_views.payment_request_cancel_view, name="request_cancel"),
]
