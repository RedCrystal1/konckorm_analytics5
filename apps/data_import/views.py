from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.decorators import accountant_or_admin_required

from .forms import ImportUploadForm
from .models import DuplicateCandidate, ImportSession
from .tasks import process_import_task
from .validators import calculate_checksum


@accountant_or_admin_required
def import_upload_view(request):
    """Загрузка файла для импорта."""
    if request.method == "POST":
        form = ImportUploadForm(request.POST, request.FILES)
        if form.is_valid():
            session = form.save(commit=False)
            session.initiated_by = request.user
            session.checksum = calculate_checksum(request.FILES["uploaded_file"])
            session.save()

            # Запуск фонового импорта
            process_import_task.delay(session.pk)

            messages.info(request, "Файл загружен. Импорт запущен в фоновом режиме.")
            return redirect("data_import:results", pk=session.pk)
    else:
        form = ImportUploadForm()
    return render(request, "data_import/import_upload.html", {"form": form})


@accountant_or_admin_required
def import_results_view(request, pk):
    """Результаты импорта."""
    session = get_object_or_404(ImportSession, pk=pk)
    logs = session.logs.all()[:100]
    return render(
        request,
        "data_import/import_results.html",
        {"session": session, "logs": logs},
    )


@accountant_or_admin_required
def duplicate_review_view(request, pk):
    """Ревью дублей."""
    session = get_object_or_404(ImportSession, pk=pk)
    duplicates = session.duplicates.select_related("existing_counterparty").filter(
        resolution=DuplicateCandidate.Resolution.PENDING
    )

    if request.method == "POST":
        dup_id = request.POST.get("duplicate_id")
        resolution = request.POST.get("resolution")
        if dup_id and resolution:
            dup = get_object_or_404(DuplicateCandidate, pk=dup_id, session=session)
            dup.resolution = resolution
            dup.resolved_by = request.user
            from django.utils import timezone

            dup.resolved_at = timezone.now()
            dup.save()
            messages.success(request, "Решение по дублю сохранено.")
            return redirect("data_import:duplicates", pk=pk)

    return render(
        request,
        "data_import/duplicate_review.html",
        {"session": session, "duplicates": duplicates},
    )


@accountant_or_admin_required
def import_history_view(request):
    """История импортов."""
    sessions = ImportSession.objects.all()[:50]
    return render(
        request,
        "data_import/import_history.html",
        {"sessions": sessions},
    )


# ── HTMX ──


@accountant_or_admin_required
def htmx_upload_progress(request, pk):
    """HTMX: прогресс импорта."""
    session = get_object_or_404(ImportSession, pk=pk)
    return render(
        request,
        "data_import/partials/_upload_progress.html",
        {"session": session},
    )


# ── Ручная корректировка импортированных данных ──


@accountant_or_admin_required
def manual_correction_view(request, pk):
    """Ручная корректировка импортированного контрагента с логированием."""
    from apps.counterparties.forms import CounterpartyForm
    from apps.counterparties.models import Counterparty
    from apps.accounts.models import ActivityLog

    session = get_object_or_404(ImportSession, pk=pk)

    # Контрагенты, созданные/обновлённые в этой сессии
    log_entries = session.logs.filter(
        level="info", object_type="Counterparty"
    ).order_by("timestamp")

    # Собираем контрагентов по code_1c из логов
    counterparties = []
    for log_entry in log_entries:
        code = log_entry.object_data.get("code_1c", "")
        if code:
            cp = Counterparty.objects.filter(code_1c=code).first()
            if cp:
                counterparties.append(cp)

    # Редактирование конкретного контрагента
    cp_id = request.GET.get("edit")
    edit_form = None
    edit_cp = None
    if cp_id:
        edit_cp = get_object_or_404(Counterparty, pk=cp_id)

        if request.method == "POST":
            old_data = {
                f.name: str(getattr(edit_cp, f.name, ""))
                for f in edit_cp._meta.fields
                if f.name not in ("id", "created_at", "updated_at")
            }

            form = CounterpartyForm(request.POST, instance=edit_cp)
            if form.is_valid():
                new_obj = form.save()

                # Логирование: что изменилось
                new_data = {
                    f.name: str(getattr(new_obj, f.name, ""))
                    for f in new_obj._meta.fields
                    if f.name not in ("id", "created_at", "updated_at")
                }
                changes = {
                    k: {"было": old_data.get(k, ""), "стало": v}
                    for k, v in new_data.items()
                    if old_data.get(k) != v
                }

                if changes:
                    ActivityLog.objects.create(
                        user=request.user,
                        action="manual_correction",
                        object_type="Counterparty",
                        object_id=str(new_obj.pk),
                        object_repr=f"Ручная корректировка: {new_obj.name} (импорт #{session.pk})",
                        details=changes,
                        ip_address=request.META.get("REMOTE_ADDR"),
                    )

                    # Лог в сессию импорта
                    ImportLog = session.logs.model
                    ImportLog.objects.create(
                        session=session,
                        level="warning",
                        message=f"Ручная корректировка: {', '.join(changes.keys())} (пользователь: {request.user})",
                        object_type="Counterparty",
                        object_data=changes,
                    )

                messages.success(request, f"Контрагент «{new_obj.name}» скорректирован. Изменения залогированы.")
                return redirect("data_import:corrections", pk=pk)
        else:
            form = CounterpartyForm(instance=edit_cp)
        edit_form = form

    return render(
        request,
        "data_import/manual_corrections.html",
        {
            "session": session,
            "counterparties": counterparties,
            "edit_cp": edit_cp,
            "edit_form": edit_form,
        },
    )
