from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("receipts/", views.goods_receipt_list_view, name="receipt_list"),
    path("receipts/<int:pk>/", views.goods_receipt_detail_view, name="receipt_detail"),
    path("payments/", views.payment_order_list_view, name="payment_list"),
    path("invoices/", views.invoice_list_view, name="invoice_list"),
    path("balances/", views.account_balance_list_view, name="balance_list"),
    # HTMX
    path("htmx/receipts/", views.htmx_receipt_table, name="htmx_receipt_table"),
]
