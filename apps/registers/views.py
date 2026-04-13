from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, render

from .filters import DebtByTermsFilter
from .models import DebtByTerms


@login_required
def debt_register_view(request):
    """Реестр задолженности по срокам с группировкой."""
    from datetime import timedelta

    from django.utils import timezone

    qs = DebtByTerms.objects.select_related(
        "counterparty", "contract", "source_document", "responsible_manager"
    ).all()

    # Менеджер по закупкам видит только свои
    if request.user.is_procurement:
        qs = qs.filter(
            Q(responsible_manager=request.user)
            | Q(counterparty__user_access__user=request.user)
        ).distinct()

    # Ручные фильтры из формы (до django-filter, чтобы работали оба)
    search = request.GET.get("search", "").strip()
    if search:
        qs = qs.filter(
            Q(counterparty__name__icontains=search)
            | Q(source_document__number__icontains=search)
        )

    status_filter = request.GET.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)

    key_only = request.GET.get("key_only")
    if key_only == "1":
        qs = qs.filter(counterparty__is_key_supplier=True)

    # Сводка
    today = timezone.now().date()
    summary = qs.aggregate(
        total_debt=Sum("amount_rub"),
        total_overdue=Sum("overdue_amount"),
    )
    summary["total_current"] = (summary["total_debt"] or 0) - (summary["total_overdue"] or 0)
    summary["record_count"] = qs.count()

    # Добавляем days_until_due к записям
    records_list = list(qs.order_by("-overdue_days", "planned_payment_date"))
    for r in records_list:
        r.days_until_due = (r.planned_payment_date - today).days if r.planned_payment_date else 999

    # Группировка
    group_by = request.GET.get("group_by")
    grouped_data = None

    if group_by == "manager":
        groups = {}
        for r in records_list:
            key = str(r.responsible_manager) if r.responsible_manager else "Не назначен"
            groups.setdefault(key, []).append(r)
        grouped_data = [
            (name, recs, sum(float(r.amount_rub) for r in recs))
            for name, recs in sorted(groups.items())
        ]

    elif group_by == "interval":
        intervals = {
            "Текущая": [],
            "Просрочка до 30 дней": [],
            "Просрочка 30–60 дней": [],
            "Просрочка 60–90 дней": [],
            "Просрочка свыше 90 дней": [],
        }
        for r in records_list:
            if r.overdue_days == 0:
                intervals["Текущая"].append(r)
            elif r.overdue_days <= 30:
                intervals["Просрочка до 30 дней"].append(r)
            elif r.overdue_days <= 60:
                intervals["Просрочка 30–60 дней"].append(r)
            elif r.overdue_days <= 90:
                intervals["Просрочка 60–90 дней"].append(r)
            else:
                intervals["Просрочка свыше 90 дней"].append(r)
        grouped_data = [
            (name, recs, sum(float(r.amount_rub) for r in recs))
            for name, recs in intervals.items()
            if recs
        ]

    elif group_by == "key_supplier":
        key_recs = [r for r in records_list if r.counterparty.is_key_supplier]
        other_recs = [r for r in records_list if not r.counterparty.is_key_supplier]
        grouped_data = []
        if key_recs:
            grouped_data.append(("Ключевые поставщики (80% закупок)", key_recs, sum(float(r.amount_rub) for r in key_recs)))
        if other_recs:
            grouped_data.append(("Прочие поставщики", other_recs, sum(float(r.amount_rub) for r in other_recs)))

    # Пагинация (только если нет группировки)
    if not grouped_data:
        paginator = Paginator(records_list, 50)
        page = paginator.get_page(request.GET.get("page"))
        records_display = page
    else:
        page = None
        records_display = records_list

    return render(
        request,
        "registers/debt_register.html",
        {
            "page_obj": page,
            "records": records_display,
            "summary": summary,
            "grouped_data": grouped_data,
        },
    )

@login_required
def debt_record_detail_view(request, pk):
    """Детальная карточка записи реестра задолженности."""
    record = get_object_or_404(
        DebtByTerms.objects.select_related(
            "counterparty", "contract", "source_document", "responsible_manager"
        ),
        pk=pk,
    )
    return render(
        request,
        "registers/debt_register_detail.html",
        {"record": record},
    )


@login_required
def htmx_debt_table(request):
    """HTMX: обновляемая таблица реестра задолженности."""
    qs = DebtByTerms.objects.select_related(
        "counterparty", "source_document", "responsible_manager"
    ).all()

    if request.user.is_procurement:
        qs = qs.filter(
            Q(responsible_manager=request.user)
            | Q(counterparty__user_access__user=request.user)
        ).distinct()

    f = DebtByTermsFilter(request.GET, queryset=qs)
    paginator = Paginator(f.qs, 50)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "registers/partials/_debt_table.html",
        {"records": page, "page_obj": page},
    )
