from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import accountant_or_admin_required, manager_or_above_required

from .forms import DepartmentForm, NomenclatureForm
from .models import Department, Nomenclature


# ── Номенклатура ──


@manager_or_above_required
def nomenclature_list_view(request):
    qs = Nomenclature.objects.all()
    kind = request.GET.get("kind")
    if kind:
        qs = qs.filter(kind=kind)
    search = request.GET.get("search", "").strip()
    if search:
        qs = qs.filter(name__icontains=search)
    return render(request, "directories/nomenclature_list.html", {"nomenclature": qs})


@accountant_or_admin_required
def nomenclature_create_view(request):
    if request.method == "POST":
        form = NomenclatureForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Номенклатура создана.")
            return redirect("directories:nomenclature_list")
    else:
        form = NomenclatureForm()
    return render(
        request,
        "directories/nomenclature_form.html",
        {"form": form, "title": "Новая номенклатура"},
    )


@accountant_or_admin_required
def nomenclature_edit_view(request, pk):
    obj = get_object_or_404(Nomenclature, pk=pk)
    if request.method == "POST":
        form = NomenclatureForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Номенклатура обновлена.")
            return redirect("directories:nomenclature_list")
    else:
        form = NomenclatureForm(instance=obj)
    return render(
        request,
        "directories/nomenclature_form.html",
        {"form": form, "title": "Редактирование номенклатуры"},
    )


# ── Подразделения ──


@manager_or_above_required
def department_list_view(request):
    qs = Department.objects.select_related("parent").all()
    return render(request, "directories/department_list.html", {"departments": qs})


@accountant_or_admin_required
def department_create_view(request):
    if request.method == "POST":
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Подразделение создано.")
            return redirect("directories:department_list")
    else:
        form = DepartmentForm()
    return render(
        request,
        "directories/department_form.html",
        {"form": form, "title": "Новое подразделение"},
    )


@accountant_or_admin_required
def department_edit_view(request, pk):
    obj = get_object_or_404(Department, pk=pk)
    if request.method == "POST":
        form = DepartmentForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Подразделение обновлено.")
            return redirect("directories:department_list")
    else:
        form = DepartmentForm(instance=obj)
    return render(
        request,
        "directories/department_form.html",
        {"form": form, "title": "Редактирование подразделения"},
    )
