"""Views для заявок на оплату (PaymentRequest).

Список + создание + детали + действия workflow (submit / approve / reject /
send_to_1c / cancel). Подключаются через apps.payments.urls.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import PaymentRequestForm, PaymentRequestRejectForm
from .models import PaymentRequest, PaymentRequestHistory
from .payment_request_service import (
    OneCSyncError,
    WorkflowError,
    approve_request,
    cancel_request,
    reject_request,
    send_to_1c,
    submit_request,
)


def _user_role(user) -> str:
    """Вычисляет ярлык роли для шаблона: 'admin' / 'accountant' / 'manager' / 'viewer'."""
    if getattr(user, "is_admin", False):
        return "admin"
    if getattr(user, "is_accountant", False):
        return "accountant"
    if getattr(user, "is_procurement", False):
        return "manager"
    return "viewer"


# ──────────────────────────────────────────────
# Список заявок
# ──────────────────────────────────────────────


@login_required
def payment_request_list_view(request):
    """Список заявок с фильтрацией по статусу.

    Менеджеры видят свои заявки + те, что они могут согласовать.
    Бухгалтеры и админы видят все заявки.
    """
    qs = PaymentRequest.objects.select_related(
        "counterparty", "contract", "related_receipt",
        "created_by", "reviewed_by",
    )

    role = _user_role(request.user)
    if role == "manager":
        # Менеджер видит только свои заявки
        qs = qs.filter(created_by=request.user)

    # Фильтр по статусу
    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    # Поиск по контрагенту/назначению
    search = request.GET.get("search", "").strip()
    if search:
        qs = qs.filter(
            Q(counterparty__name__icontains=search)
            | Q(purpose__icontains=search)
            | Q(one_c_doc_number__icontains=search)
        )

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page"))

    # Подсчёт по статусам для виджета фильтров
    base_for_counts = PaymentRequest.objects.all()
    if role == "manager":
        base_for_counts = base_for_counts.filter(created_by=request.user)
    counts = {
        s.value: base_for_counts.filter(status=s.value).count()
        for s in PaymentRequest.Status
    }
    counts["total"] = base_for_counts.count()

    return render(
        request,
        "payments/payment_request_list.html",
        {
            "page_obj": page,
            "requests": page,
            "status_filter": status_filter,
            "search": search,
            "counts": counts,
            "statuses": PaymentRequest.Status,
            "role": role,
        },
    )


# ──────────────────────────────────────────────
# Создание / редактирование
# ──────────────────────────────────────────────


@login_required
def payment_request_create_view(request):
    """Менеджер создаёт новую заявку.

    Если в GET-параметрах есть ?receipt=N, форма предзаполнится
    данными из соответствующего GoodsReceipt.
    """
    initial = {}
    receipt_id = request.GET.get("receipt")
    if receipt_id:
        from apps.documents.models import GoodsReceipt
        try:
            receipt = GoodsReceipt.objects.select_related(
                "counterparty", "contract"
            ).get(pk=receipt_id)
            initial = {
                "counterparty": receipt.counterparty_id,
                "contract": receipt.contract_id,
                "related_receipt": receipt.pk,
                "amount": receipt.amount - receipt.paid_amount,
                "planned_date": receipt.payment_due_date,
                "purpose": (
                    f"Оплата по поступлению №{receipt.number} от {receipt.date:%d.%m.%Y}"
                    + (f", договор {receipt.contract.number}" if receipt.contract else "")
                ),
            }
        except GoodsReceipt.DoesNotExist:
            messages.error(request, "Указанное поступление не найдено.")

    if request.method == "POST":
        form = PaymentRequestForm(request.POST)
        if form.is_valid():
            pr = form.save(commit=False)
            pr.created_by = request.user
            pr.status = PaymentRequest.Status.DRAFT
            pr.save()
            PaymentRequestHistory.objects.create(
                request=pr,
                from_status="",
                to_status=pr.status,
                actor=request.user,
                comment="Создана заявка",
            )
            messages.success(request, f"Заявка #{pr.id} создана как черновик.")
            # Если пользователь нажал «Отправить сразу» — перевод в submitted
            if request.POST.get("action") == "submit":
                try:
                    submit_request(pr, request.user)
                    messages.success(request, "Заявка отправлена на согласование бухгалтеру.")
                except WorkflowError as exc:
                    messages.error(request, str(exc))
            return redirect("payments:request_detail", pk=pr.pk)
    else:
        form = PaymentRequestForm(initial=initial)

    return render(
        request,
        "payments/payment_request_form.html",
        {
            "form": form,
            "title": "Новая заявка на оплату",
            "is_create": True,
        },
    )


@login_required
def payment_request_update_view(request, pk):
    pr = get_object_or_404(
        PaymentRequest.objects.select_related("counterparty"), pk=pk
    )
    if not pr.can_edit:
        messages.error(request, "Заявку в этом статусе редактировать нельзя.")
        return redirect("payments:request_detail", pk=pr.pk)
    if pr.created_by != request.user and not _user_role(request.user) in ("admin",):
        messages.error(request, "Редактировать может только автор или администратор.")
        return redirect("payments:request_detail", pk=pr.pk)

    if request.method == "POST":
        form = PaymentRequestForm(request.POST, instance=pr)
        if form.is_valid():
            form.save()
            messages.success(request, "Заявка обновлена.")
            if request.POST.get("action") == "submit":
                try:
                    submit_request(pr, request.user)
                    messages.success(request, "Заявка отправлена на согласование.")
                except WorkflowError as exc:
                    messages.error(request, str(exc))
            return redirect("payments:request_detail", pk=pr.pk)
    else:
        form = PaymentRequestForm(instance=pr)

    return render(
        request,
        "payments/payment_request_form.html",
        {
            "form": form,
            "title": f"Редактирование заявки #{pr.id}",
            "is_create": False,
            "payment_request": pr,
        },
    )


# ──────────────────────────────────────────────
# Карточка заявки
# ──────────────────────────────────────────────


@login_required
def payment_request_detail_view(request, pk):
    pr = get_object_or_404(
        PaymentRequest.objects.select_related(
            "counterparty", "contract", "related_receipt",
            "created_by", "reviewed_by",
        ),
        pk=pk,
    )
    role = _user_role(request.user)

    # Менеджер может видеть только свои заявки
    if role == "manager" and pr.created_by != request.user:
        messages.error(request, "У вас нет доступа к этой заявке.")
        return redirect("payments:request_list")

    history = pr.history.select_related("actor").all()
    reject_form = PaymentRequestRejectForm()

    # Доступные пользователю действия
    actions = {
        "edit": pr.can_edit and (pr.created_by == request.user or role == "admin"),
        "submit": pr.can_submit and (pr.created_by == request.user or role == "admin"),
        "approve": pr.can_approve and role in ("accountant", "admin"),
        "reject": pr.can_reject and role in ("accountant", "admin"),
        "send_to_1c": pr.can_send_to_1c and role in ("accountant", "admin"),
        "cancel": pr.can_cancel and (
            pr.created_by == request.user or role in ("accountant", "admin")
        ),
    }

    return render(
        request,
        "payments/payment_request_detail.html",
        {
            "payment_request": pr,
            "history": history,
            "reject_form": reject_form,
            "role": role,
            "actions": actions,
        },
    )


# ──────────────────────────────────────────────
# Действия workflow (POST)
# ──────────────────────────────────────────────


@login_required
@require_POST
def payment_request_submit_view(request, pk):
    pr = get_object_or_404(PaymentRequest, pk=pk)
    if pr.created_by != request.user and _user_role(request.user) != "admin":
        messages.error(request, "Отправить может только автор или администратор.")
        return redirect("payments:request_detail", pk=pr.pk)
    try:
        submit_request(pr, request.user)
        messages.success(request, "Заявка отправлена на согласование бухгалтеру.")
    except WorkflowError as exc:
        messages.error(request, str(exc))
    return redirect("payments:request_detail", pk=pr.pk)


@login_required
@require_POST
def payment_request_approve_view(request, pk):
    pr = get_object_or_404(PaymentRequest, pk=pk)
    if _user_role(request.user) not in ("accountant", "admin"):
        messages.error(request, "Согласовать может только бухгалтер или администратор.")
        return redirect("payments:request_detail", pk=pr.pk)
    try:
        approve_request(pr, request.user)
        messages.success(request, "Заявка одобрена. Теперь её можно отправить в 1С.")
    except WorkflowError as exc:
        messages.error(request, str(exc))
    return redirect("payments:request_detail", pk=pr.pk)


@login_required
@require_POST
def payment_request_reject_view(request, pk):
    pr = get_object_or_404(PaymentRequest, pk=pk)
    if _user_role(request.user) not in ("accountant", "admin"):
        messages.error(request, "Отклонить может только бухгалтер или администратор.")
        return redirect("payments:request_detail", pk=pr.pk)
    form = PaymentRequestRejectForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Укажите причину отклонения.")
        return redirect("payments:request_detail", pk=pr.pk)
    try:
        reject_request(pr, request.user, form.cleaned_data["reason"])
        messages.success(request, "Заявка отклонена. Менеджер увидит причину.")
    except WorkflowError as exc:
        messages.error(request, str(exc))
    return redirect("payments:request_detail", pk=pr.pk)


@login_required
@require_POST
def payment_request_send_to_1c_view(request, pk):
    pr = get_object_or_404(PaymentRequest, pk=pk)
    if _user_role(request.user) not in ("accountant", "admin"):
        messages.error(request, "Отправить в 1С может только бухгалтер или администратор.")
        return redirect("payments:request_detail", pk=pr.pk)
    # Флаг "провести в 1С" из формы (по умолчанию - черновик)
    post_flag = request.POST.get("post") == "1"
    try:
        send_to_1c(pr, request.user, post=post_flag)
        action = "проведено в 1С" if post_flag else "отправлено в 1С (черновик)"
        messages.success(
            request,
            f"Платёжное поручение №{pr.one_c_doc_number} {action}."
        )
    except (WorkflowError, OneCSyncError) as exc:
        messages.error(request, f"Не удалось отправить в 1С: {exc}")
    return redirect("payments:request_detail", pk=pr.pk)


@login_required
@require_POST
def payment_request_cancel_view(request, pk):
    pr = get_object_or_404(PaymentRequest, pk=pk)
    role = _user_role(request.user)
    if pr.created_by != request.user and role not in ("accountant", "admin"):
        messages.error(request, "Отменить может автор или бухгалтер/администратор.")
        return redirect("payments:request_detail", pk=pr.pk)
    try:
        cancel_request(pr, request.user)
        messages.success(request, "Заявка отменена.")
    except WorkflowError as exc:
        messages.error(request, str(exc))
    return redirect("payments:request_detail", pk=pr.pk)
