from django.urls import path

from . import views

app_name = "registers"

urlpatterns = [
    path("debt/", views.debt_register_view, name="debt_register"),
    path("debt/<int:pk>/", views.debt_record_detail_view, name="debt_detail"),
    # HTMX
    path("htmx/debt-table/", views.htmx_debt_table, name="htmx_debt_table"),
]
