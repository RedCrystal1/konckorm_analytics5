from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    # Документация
    path("", views.api_docs, name="docs"),

    # Входящий поток: 1С → Платформа
    path("sync/counterparties/", views.sync_counterparties, name="sync_counterparties"),
    path("sync/contracts/", views.sync_contracts, name="sync_contracts"),
    path("sync/documents/receipts/", views.sync_receipts, name="sync_receipts"),
    path("sync/documents/payments/", views.sync_payments, name="sync_payments"),
    path("sync/balances/", views.sync_balances, name="sync_balances"),

    # Исходящий поток: Платформа → 1С
    path("export/reconciliations/", views.export_reconciliations, name="export_reconciliations"),
    path("export/debt-status/", views.export_debt_status, name="export_debt_status"),
    path("export/payment-recommendations/", views.export_payment_recommendations, name="export_payment_recommendations"),

    # Статус
    path("status/", views.api_status, name="status"),
]
