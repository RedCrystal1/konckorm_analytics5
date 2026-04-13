from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import accountant_or_admin_required, manager_or_above_required

from .filters import DiscrepancyFilter
from .forms import DiscrepancyStatusForm, ReconciliationActForm
from .models import Discrepancy, ReconciliationAct
from .services import generate_reconciliation_act
from django.contrib import messages
from .models import ReconciliationAct

@manager_or_above_required
def discrepancy_list_view(request):
    """Реестр расхождений."""
    qs = Discrepancy.objects.select_related(
        "counterparty", "reconciliation_act", "responsible"
    ).all()
    f = DiscrepancyFilter(request.GET, queryset=qs)
    paginator = Paginator(f.qs, 25)
    page = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "reconciliation/discrepancy_list.html",
        {"page_obj": page, "filter": f, "discrepancies": page},
    )


@manager_or_above_required
def discrepancy_detail_view(request, pk):
    """Карточка расхождения."""
    discrepancy = get_object_or_404(
        Discrepancy.objects.select_related(
            "counterparty", "reconciliation_act", "responsible"
        ),
        pk=pk,
    )
    return render(
        request,
        "reconciliation/discrepancy_detail.html",
        {"discrepancy": discrepancy},
    )


@accountant_or_admin_required
def discrepancy_update_status(request, pk):
    """Обновление статуса расхождения."""
    discrepancy = get_object_or_404(Discrepancy, pk=pk)
    if request.method == "POST":
        form = DiscrepancyStatusForm(request.POST, instance=discrepancy)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.status == Discrepancy.Status.RESOLVED:
                from django.utils import timezone

                obj.resolved_at = timezone.now()
            obj.save()
            messages.success(request, "Статус расхождения обновлён.")
            return redirect("reconciliation:discrepancy_detail", pk=pk)
    else:
        form = DiscrepancyStatusForm(instance=discrepancy)
    return render(
        request,
        "reconciliation/discrepancy_status_form.html",
        {"form": form, "discrepancy": discrepancy},
    )


# @accountant_or_admin_required
# def generate_reconciliation_act_view(request):
#     """Генерация акта сверки."""
#     if request.method == "POST":
#         form = ReconciliationActForm(request.POST)
#         if form.is_valid():
#             act = generate_reconciliation_act(
#                 counterparty=form.cleaned_data["counterparty"],
#                 period_start=form.cleaned_data["period_start"],
#                 period_end=form.cleaned_data["period_end"],
#                 user=request.user,
#             )
#             messages.success(request, f"Акт сверки сформирован (сальдо: {act.our_balance}).")
#             return redirect("reconciliation:discrepancy_list")
#     else:
#         form = ReconciliationActForm()
#     return render(
#         request,
#         "reconciliation/reconciliation_act_form.html",
#         {"form": form},
#     )
@accountant_or_admin_required
def generate_reconciliation_act_view(request):
    """Формирование акта сверки."""
    from .forms import ReconciliationActForm
    from .services import generate_reconciliation_act

    if request.method == "POST":
        form = ReconciliationActForm(request.POST)
        if form.is_valid():
            act = generate_reconciliation_act(
                counterparty=form.cleaned_data["counterparty"],
                period_start=form.cleaned_data["period_start"],
                period_end=form.cleaned_data["period_end"],
                user=request.user,
            )
            messages.success(
                request,
                f"Акт сверки сформирован. Наше сальдо: {act.our_balance:,.0f} руб. "
                f"Расхождений: {act.discrepancies.count()}"
            )
            return redirect("reconciliation:act_detail", pk=act.pk)
    else:
        form = ReconciliationActForm()

    return render(
        request,
        "reconciliation/reconciliation_act_form.html",
        {"form": form},
    )
@accountant_or_admin_required
def reconciliation_act_detail_view(request, pk):
    """Детали акта сверки с возможностью ввести сальдо контрагента."""
    from .services import check_reconciliation_match

    act = get_object_or_404(
        ReconciliationAct.objects.select_related("counterparty", "created_by"),
        pk=pk,
    )
    discrepancies = act.discrepancies.all()

    # Форма ввода сальдо контрагента
    if request.method == "POST" and "their_balance" in request.POST:
        try:
            from decimal import Decimal
            their_balance = Decimal(request.POST["their_balance"].replace(",", ".").replace(" ", ""))
            is_matched = check_reconciliation_match(act, their_balance)
            if is_matched:
                messages.success(request, "Данные совпали! Акт сверки закрыт.")
            else:
                messages.warning(request, f"Обнаружено расхождение: {abs(act.our_balance - their_balance):,.0f} руб.")
            return redirect("reconciliation:act_detail", pk=pk)
        except Exception as e:
            messages.error(request, f"Ошибка: {e}")

    return render(
        request,
        "reconciliation/act_detail.html",
        {"act": act, "discrepancies": discrepancies},
    )