from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import accountant_or_admin_required
from apps.analytics.models import AnalyticsSnapshot
from apps.documents.models import AccountBalance

from .filters import ContractFilter
from .forms import ContractForm, CounterpartyForm
from .models import Contract, Counterparty


@login_required
def counterparty_list_view(request):
    qs = Counterparty.objects.select_related("responsible_manager").all()
    if request.user.is_procurement:
        qs = qs.filter(
            Q(responsible_manager=request.user)
            | Q(user_access__user=request.user)
        ).distinct()

    search = request.GET.get("search", "").strip()
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(inn__icontains=search))

    is_key = request.GET.get("is_key_supplier")
    if is_key == "true":
        qs = qs.filter(is_key_supplier=True)
    elif is_key == "false":
        qs = qs.filter(is_key_supplier=False)

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "counterparties/counterparty_list.html",
        {"page_obj": page, "counterparties": page},
    )

@login_required
def counterparty_detail_view(request, pk):
    from datetime import date, timedelta
    from apps.reconciliation.models import Discrepancy, ReconciliationAct
    from apps.registers.models import DebtByTerms

    cp = get_object_or_404(
        Counterparty.objects.select_related("responsible_manager"), pk=pk
    )
    contracts = cp.contracts.all()

    # Период графика: 7 / 14 / 30 дней
    # Период графика в бухгалтерских терминах:
    # 30 — месяц, 90 — квартал, 180 — полугодие, 365 — год
    allowed_periods = [30, 90, 180, 365]
    try:
        period = int(request.GET.get("period", 30))
    except (TypeError, ValueError):
        period = 30
    if period not in allowed_periods:
        period = 30

    # Сводка задолженности (на последнюю дату записи)
    latest_date = (
        DebtByTerms.objects.filter(counterparty=cp)
        .order_by("-record_date")
        .values_list("record_date", flat=True)
        .first()
    )
    debt_qs = (
        DebtByTerms.objects.filter(counterparty=cp, record_date=latest_date)
        if latest_date else DebtByTerms.objects.none()
    )
    debt_summary = {
        "total_debt": debt_qs.aggregate(s=Sum("amount_rub"))["s"] or 0,
        "overdue_amount": debt_qs.exclude(status="current").aggregate(s=Sum("amount_rub"))["s"] or 0,
        "unpaid_count": debt_qs.count(),
        "overdue_count": debt_qs.exclude(status="current").count(),
    }

    # История задолженности за выбранный период
    today = date.today()
    start = today - timedelta(days=period)

    raw_history = (
        DebtByTerms.objects.filter(counterparty=cp, record_date__gte=start)
        .values("record_date")
        .annotate(
            total_amount=Sum("amount_rub"),
            overdue_total=Sum("amount_rub", filter=~Q(status="current")),
        )
        .order_by("record_date")
    )

    hist_map = {r["record_date"]: r for r in raw_history}
    debt_history = []
    last_amount = 0
    last_overdue = 0
    for i in range(period + 1):
        d = start + timedelta(days=i)
        if d in hist_map:
            last_amount = float(hist_map[d]["total_amount"] or 0)
            last_overdue = float(hist_map[d]["overdue_total"] or 0)
        debt_history.append({
            "record_date": d,
            "amount_rub": last_amount,
            "overdue_amount": last_overdue,
        })

    if not hist_map:
        debt_history = []

    # Последняя сверка
    last_reconciliation = ReconciliationAct.objects.filter(counterparty=cp).order_by("-created_at").first()
    open_discrepancies = Discrepancy.objects.filter(counterparty=cp, status="open") if last_reconciliation else []

    # Открытые (неоплаченные) документы — для блока «Открытые документы»
    from apps.documents.models import GoodsReceipt
    open_documents = (
        GoodsReceipt.objects.filter(counterparty=cp, is_paid=False)
        .order_by("-date")[:10]
    )
    # Дни просрочки для каждого документа
    for d in open_documents:
        if d.payment_due_date:
            d.days_overdue = (today - d.payment_due_date).days
        else:
            d.days_overdue = 0

    # ─────────────────────────────────────────────────────────────
    # Сальдо счёта 60.01 / 60.02 (из AccountBalance) + сверка
    # ─────────────────────────────────────────────────────────────
    # Опциональный пересчёт сальдо 60 по запросу пользователя:
    # `?recalc_60=1` запускает management-команду recalc_account_60
    # для текущего контрагента. Доступно только админу/бухгалтеру.
    if request.GET.get("recalc_60") == "1" and (
        getattr(request.user, "is_admin", False)
        or getattr(request.user, "is_accountant", False)
    ):
        from django.core.management import call_command
        try:
            call_command("recalc_account_60", counterparty=cp.id)
            messages.success(request, "Сальдо счёта 60 пересчитано.")
        except Exception as exc:  # noqa: BLE001
            messages.error(request, f"Ошибка пересчёта сальдо: {exc}")

    acc60_01 = (
        AccountBalance.objects
        .filter(counterparty=cp, account="60.01")
        .order_by("-balance_date")
        .first()
    )
    acc60_02 = (
        AccountBalance.objects
        .filter(counterparty=cp, account="60.02")
        .order_by("-balance_date")
        .first()
    )
    acc60_date = None
    if acc60_01:
        acc60_date = acc60_01.balance_date
    elif acc60_02:
        acc60_date = acc60_02.balance_date

    # Сверка: совпадает ли расчётный долг (из DebtByTerms) с сальдо 60.01?
    # acc60_match: True — совпадает; False — расхождение; None — нет данных.
    acc60_match = None
    acc60_diff = 0
    debt_calc = float(debt_summary["total_debt"] or 0)
    debt_acc60 = float(acc60_01.balance) if acc60_01 else 0
    if acc60_01 is None and debt_calc == 0:
        # Оба источника пустые — считаем что совпадает
        acc60_match = True
    elif acc60_01 is not None:
        acc60_diff = abs(debt_calc - debt_acc60)
        # Совпадает если расхождение < 1 рубль (для арифметической точности)
        acc60_match = acc60_diff < 1

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
            "chart_period": period,
            "chart_periods": allowed_periods,
            "open_documents": open_documents,
            "today": today,
            # Сальдо по счёту 60 + результат сверки
            "acc60_01": acc60_01,
            "acc60_02": acc60_02,
            "acc60_date": acc60_date,
            "acc60_match": acc60_match,
            "acc60_diff": acc60_diff,
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
    # Документы по этому договору
    # receipts = contract.receipts.order_by("-date")[:10]
    from apps.documents.models import GoodsReceipt

    receipts = GoodsReceipt.objects.filter(
        counterparty=contract.counterparty
    ).order_by("-date")[:10]
    payments = contract.payment_orders.order_by("-date")[:10] if hasattr(contract, "payment_orders") else []
    return render(
        request,
        "counterparties/contract_detail.html",
        {"contract": contract, "receipts": receipts, "payments": payments},
    )


@accountant_or_admin_required
def contract_create_view(request):
    """Создание нового договора."""
    # Предзаполнение контрагента из GET-параметра
    initial = {}
    cp_pk = request.GET.get("counterparty")
    if cp_pk:
        initial["counterparty"] = cp_pk

    if request.method == "POST":
        form = ContractForm(request.POST)
        if form.is_valid():
            contract = form.save()
            messages.success(request, f"Договор №{contract.number} создан.")
            return redirect("counterparties:contract_detail", pk=contract.pk)
    else:
        form = ContractForm(initial=initial)
    return render(
        request,
        "counterparties/contract_form.html",
        {"form": form, "title": "Новый договор"},
    )


@accountant_or_admin_required
def contract_update_view(request, pk):
    """Редактирование договора."""
    contract = get_object_or_404(Contract, pk=pk)
    if request.method == "POST":
        form = ContractForm(request.POST, instance=contract)
        if form.is_valid():
            form.save()
            messages.success(request, f"Договор №{contract.number} обновлён.")
            return redirect("counterparties:contract_detail", pk=contract.pk)
    else:
        form = ContractForm(instance=contract)
    return render(
        request,
        "counterparties/contract_form.html",
        {"form": form, "title": f"Редактирование договора №{contract.number}", "contract": contract},
    )


# ── HTMX endpoints ──


@login_required
def htmx_counterparty_table(request):
    """HTMX: обновляемая таблица контрагентов."""
    qs = Counterparty.objects.select_related("responsible_manager").all()
    search = request.GET.get("search", "").strip()
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(inn__icontains=search))
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
    from apps.registers.models import DebtByTerms

    cp = get_object_or_404(Counterparty, pk=pk)
    records = DebtByTerms.objects.filter(counterparty=cp).order_by("-record_date")[:30]
    return render(
        request,
        "counterparties/partials/_debt_history.html",
        {"records": records},
    )


@login_required
def htmx_counterparty_chart(request, pk):
    cp = get_object_or_404(Counterparty, pk=pk)
    snapshots = list(
        AnalyticsSnapshot.objects.order_by("date").values("date", "total_debt", "overdue_debt")[:60]
    )
    history = [{"record_date": s["date"], "amount_rub": s["total_debt"]} for s in snapshots]
    return render(
        request,
        "counterparties/partials/_debt_chart.html",
        {"history": history, "counterparty": cp},
    )
