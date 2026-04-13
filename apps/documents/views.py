from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from apps.accounts.decorators import manager_or_above_required

from .filters import GoodsReceiptFilter, InvoiceFilter, PaymentOrderFilter
from .models import AccountBalance, GoodsReceipt, Invoice, PaymentOrder


@login_required
def goods_receipt_list_view(request):
    qs = GoodsReceipt.objects.select_related("counterparty", "contract").all()
    f = GoodsReceiptFilter(request.GET, queryset=qs)
    paginator = Paginator(f.qs, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "documents/document_list.html",
        {
            "page_obj": page,
            "filter": f,
            "documents": page,
            "title": "Поступления товаров и услуг",
            "doc_type": "receipt",
        },
    )


@login_required
def goods_receipt_detail_view(request, pk):
    receipt = get_object_or_404(
        GoodsReceipt.objects.select_related("counterparty", "contract", "created_by"),
        pk=pk,
    )
    items = receipt.items.select_related("nomenclature").all()
    payments = receipt.payments.all()
    return render(
        request,
        "documents/document_detail.html",
        {
            "document": receipt,
            "items": items,
            "payments": payments,
            "title": f"Поступление №{receipt.number}",
        },
    )


@login_required
def payment_order_list_view(request):
    qs = PaymentOrder.objects.select_related("counterparty", "contract").all()
    f = PaymentOrderFilter(request.GET, queryset=qs)
    paginator = Paginator(f.qs, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "documents/document_list.html",
        {
            "page_obj": page,
            "filter": f,
            "documents": page,
            "title": "Платёжные поручения",
            "doc_type": "payment",
        },
    )


@login_required
def invoice_list_view(request):
    qs = Invoice.objects.select_related("counterparty", "contract").all()
    f = InvoiceFilter(request.GET, queryset=qs)
    paginator = Paginator(f.qs, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "documents/document_list.html",
        {
            "page_obj": page,
            "filter": f,
            "documents": page,
            "title": "Счета на оплату",
            "doc_type": "invoice",
        },
    )


@login_required
def account_balance_list_view(request):
    """Остатки по счетам бухучёта."""
    from .models import AccountBalance

    qs = AccountBalance.objects.select_related("counterparty", "contract").order_by("-balance_date")

    # Фильтр по счёту
    account_filter = request.GET.get("account")
    if account_filter:
        qs = qs.filter(account=account_filter)

    # Фильтр по контрагенту
    search = request.GET.get("search", "").strip()
    if search:
        qs = qs.filter(counterparty__name__icontains=search)

    # Агрегация по счетам
    from django.db.models import Sum
    summary = AccountBalance.objects.values("account").annotate(
        total_debit=Sum("debit"),
        total_credit=Sum("credit"),
        total_balance=Sum("balance"),
    ).order_by("account")

    from django.core.paginator import Paginator
    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "documents/balance_list.html",
        {
            "balances": page,
            "page_obj": page,
            "summary": summary,
            "account_filter": account_filter,
            "search": search,
        },
    )

# ── HTMX ──


@login_required
def htmx_receipt_table(request):
    qs = GoodsReceipt.objects.select_related("counterparty").all()
    f = GoodsReceiptFilter(request.GET, queryset=qs)
    paginator = Paginator(f.qs, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "documents/partials/_document_table.html",
        {"documents": page, "page_obj": page, "doc_type": "receipt"},
    )
