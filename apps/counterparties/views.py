from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import accountant_or_admin_required

from .filters import ContractFilter, CounterpartyFilter
from .forms import ContractForm, CounterpartyForm
from .models import Contract, Counterparty
from .services import create_history_snapshot, get_counterparty_debt_summary


@login_required
def counterparty_list_view(request):
    """Список контрагентов с фильтрацией."""
    qs = Counterparty.objects.select_related("responsible_manager").all()

    # Менеджер по закупкам видит только своих
    if request.user.is_procurement:
        qs = qs.filter(
            Q(responsible_manager=request.user)
            | Q(user_access__user=request.user)
        ).distinct()

    f = CounterpartyFilter(request.GET, queryset=qs)
    paginator = Paginator(f.qs, 25)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "counterparties/counterparty_list.html",
        {"page_obj": page, "filter": f, "counterparties": page},
    )


@login_required
def counterparty_detail_view(request, pk):
    """Карточка контрагента."""
    cp = get_object_or_404(
        Counterparty.objects.select_related("responsible_manager"), pk=pk
    )

    # Проверка доступа для менеджеров по закупкам
    if request.user.is_procurement:
        has_access = (
            cp.responsible_manager == request.user
            or cp.user_access.filter(user=request.user).exists()
        )
        if not has_access:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

    contracts = cp.contracts.all()
    debt_summary = get_counterparty_debt_summary(cp)

    # История задолженности для графика
    from apps.registers.models import DebtByTerms

    debt_history = list(
        DebtByTerms.objects.filter(counterparty=cp)
        .order_by("record_date")
        .values("record_date", "amount_rub", "overdue_amount")[:60]
    )

    # Последняя сверка
    from apps.reconciliation.models import Discrepancy, ReconciliationAct

    last_reconciliation = (
        ReconciliationAct.objects.filter(counterparty=cp)
        .order_by("-period_end")
        .first()
    )
    open_discrepancies = []
    if last_reconciliation:
        open_discrepancies = list(
            Discrepancy.objects.filter(
                reconciliation_act=last_reconciliation,
                status__in=[Discrepancy.Status.OPEN, Discrepancy.Status.IN_PROGRESS],
            )
        )

    return render(
        request,
        "counterparties/counterparty_detail.html",
        {
            "counterparty": cp,
            "contracts": contracts,
            "debt_summary": debt_summary,
            "debt_history": debt_history,
            "last_reconciliation": last_reconciliation,
            "open_discrepancies": open_discrepancies,
        },
    )


@accountant_or_admin_required
def counterparty_create_view(request):
    if request.method == "POST":
        form = CounterpartyForm(request.POST)
        if form.is_valid():
            cp = form.save()
            messages.success(request, f"Контрагент «{cp.name}» создан.")
            return redirect("counterparties:detail", pk=cp.pk)
    else:
        form = CounterpartyForm()
    return render(
        request,
        "counterparties/counterparty_form.html",
        {"form": form, "title": "Новый контрагент"},
    )


@accountant_or_admin_required
def counterparty_update_view(request, pk):
    cp = get_object_or_404(Counterparty, pk=pk)
    if request.method == "POST":
        form = CounterpartyForm(request.POST, instance=cp)
        if form.is_valid():
            create_history_snapshot(cp, user=request.user)
            form.save()
            messages.success(request, f"Контрагент «{cp.name}» обновлён.")
            return redirect("counterparties:detail", pk=cp.pk)
    else:
        form = CounterpartyForm(instance=cp)
    return render(
        request,
        "counterparties/counterparty_form.html",
        {"form": form, "title": "Редактирование контрагента", "counterparty": cp},
    )


@login_required
def contract_list_view(request):
    qs = Contract.objects.select_related("counterparty").all()
    if request.user.is_procurement:
        qs = qs.filter(
            Q(counterparty__responsible_manager=request.user)
            | Q(counterparty__user_access__user=request.user)
        ).distinct()
    f = ContractFilter(request.GET, queryset=qs)
    paginator = Paginator(f.qs, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "counterparties/contract_list.html",
        {"page_obj": page, "filter": f, "contracts": page},
    )


@login_required
def contract_detail_view(request, pk):
    contract = get_object_or_404(
        Contract.objects.select_related("counterparty"), pk=pk
    )
    return render(
        request,
        "counterparties/contract_detail.html",
        {"contract": contract},
    )


# ── HTMX endpoints ──


@login_required
def htmx_counterparty_table(request):
    """HTMX: обновляемая таблица контрагентов."""
    qs = Counterparty.objects.select_related("responsible_manager").all()
    if request.user.is_procurement:
        qs = qs.filter(
            Q(responsible_manager=request.user)
            | Q(user_access__user=request.user)
        ).distinct()

    search = request.GET.get("search", "").strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search) | Q(inn__icontains=search)
        )

    is_key = request.GET.get("is_key_supplier")
    if is_key == "true":
        qs = qs.filter(is_key_supplier=True)
    elif is_key == "false":
        qs = qs.filter(is_key_supplier=False)

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "counterparties/partials/_counterparty_table.html",
        {"counterparties": page, "page_obj": page},
    )


@login_required
def htmx_debt_history(request, pk):
    """HTMX: история задолженности контрагента."""
    cp = get_object_or_404(Counterparty, pk=pk)
    from apps.registers.models import DebtByTerms

    records = DebtByTerms.objects.filter(counterparty=cp).order_by("-record_date")[:50]
    return render(
        request,
        "counterparties/partials/_debt_history.html",
        {"records": records, "counterparty": cp},
    )


@login_required
def htmx_counterparty_chart(request, pk):
    """HTMX: график задолженности контрагента (возвращает данные для Chart.js)."""
    cp = get_object_or_404(Counterparty, pk=pk)
    from apps.registers.models import DebtByTerms

    records = (
        DebtByTerms.objects.filter(counterparty=cp)
        .order_by("record_date")
        .values("record_date", "amount_rub", "overdue_amount")[:30]
    )
    return render(
        request,
        "counterparties/partials/_debt_chart.html",
        {"records": list(records), "counterparty": cp},
    )
