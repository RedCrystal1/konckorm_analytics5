from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import accountant_or_admin_required, manager_or_above_required
from apps.accounts.models import ActivityLog

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


@accountant_or_admin_required
def update_payment_status_view(request, pk):
    """Ручное изменение статуса оплаты документа."""
    receipt = get_object_or_404(GoodsReceipt, pk=pk)

    if request.method == "POST":
        action = request.POST.get("action")

        # Сохраняем старые значения для аудита
        old_is_paid = receipt.is_paid
        old_paid_amount = receipt.paid_amount

        if action == "mark_paid":
            # Отметить как полностью оплаченный
            receipt.paid_amount = receipt.amount
            receipt.is_paid = True
            receipt.save(update_fields=["paid_amount", "is_paid"])
            messages.success(request, f"Документ №{receipt.number} отмечен как оплаченный.")

        elif action == "mark_unpaid":
            # Вернуть в статус неоплаченного
            receipt.paid_amount = Decimal("0")
            receipt.is_paid = False
            receipt.save(update_fields=["paid_amount", "is_paid"])
            messages.success(request, f"Документ №{receipt.number} возвращён в статус неоплаченного.")

        elif action == "set_partial":
            # Частичная оплата
            try:
                amount_str = request.POST.get("paid_amount", "0").replace(",", ".").replace(" ", "")
                new_paid = Decimal(amount_str)

                if new_paid < 0:
                    messages.error(request, "Сумма оплаты не может быть отрицательной.")
                    return redirect("documents:receipt_detail", pk=pk)

                if new_paid > receipt.amount:
                    messages.error(request, f"Сумма оплаты не может превышать сумму документа ({receipt.amount:,.0f} руб.).")
                    return redirect("documents:receipt_detail", pk=pk)

                receipt.paid_amount = new_paid
                receipt.is_paid = new_paid >= receipt.amount
                receipt.save(update_fields=["paid_amount", "is_paid"])

                if receipt.is_paid:
                    messages.success(request, f"Документ №{receipt.number} полностью оплачен ({new_paid:,.0f} руб.).")
                else:
                    messages.success(request, f"Оплата документа №{receipt.number} обновлена: {new_paid:,.0f} из {receipt.amount:,.0f} руб.")

            except (InvalidOperation, ValueError):
                messages.error(request, "Введите корректную сумму.")
                return redirect("documents:receipt_detail", pk=pk)

        # Логирование изменения
        ActivityLog.objects.create(
            user=request.user,
            action="payment_status_change",
            object_type="GoodsReceipt",
            object_id=str(receipt.pk),
            object_repr=f"Изменение оплаты: Поступление №{receipt.number}",
            details={
                "was_paid": old_is_paid,
                "was_amount": str(old_paid_amount),
                "now_paid": receipt.is_paid,
                "now_amount": str(receipt.paid_amount),
                "action": action,
            },
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        # Обновляем регистр задолженности
        try:
            from apps.registers.services import update_debt_statuses
            update_debt_statuses()
        except Exception:
            pass

    return redirect("documents:receipt_detail", pk=pk)


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


@manager_or_above_required
def account_balance_list_view(request):
    """Остатки по счетам бухучёта."""
    from django.db.models import Sum

    qs = AccountBalance.objects.select_related("counterparty", "contract").order_by("-balance_date")

    account_filter = request.GET.get("account")
    if account_filter:
        qs = qs.filter(account=account_filter)

    search = request.GET.get("search", "").strip()
    if search:
        qs = qs.filter(counterparty__name__icontains=search)

    summary = AccountBalance.objects.values("account").annotate(
        total_debit=Sum("debit"),
        total_credit=Sum("credit"),
        total_balance=Sum("balance"),
    ).order_by("account")

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
            "title": "Остатки по счетам",
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
