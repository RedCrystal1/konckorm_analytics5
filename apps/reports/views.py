from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import render

from apps.accounts.decorators import manager_or_above_required

from .forms import ReportForm


@manager_or_above_required
def report_generator_view(request):
    """Генератор отчётов: форма выбора параметров."""
    if request.method == "POST":
        form = ReportForm(request.POST)
        if form.is_valid():
            report_type = form.cleaned_data["report_type"]
            output_format = form.cleaned_data["output_format"]
            date_from = form.cleaned_data.get("date_from")
            date_to = form.cleaned_data.get("date_to")
            counterparty = form.cleaned_data.get("counterparty")

            try:
                if output_format == "excel":
                    buf = _generate_excel_sync(report_type, date_from, date_to, counterparty)
                    filename = f"{report_type}.xlsx"
                    content_type = (
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    buf = _generate_pdf_sync(report_type, date_from, date_to, counterparty)
                    filename = f"{report_type}.pdf"
                    content_type = "application/pdf"

                return FileResponse(buf, as_attachment=True, filename=filename, content_type=content_type)

            except Exception as e:
                messages.error(request, f"Ошибка генерации отчёта: {e}")
    else:
        form = ReportForm()

    return render(request, "reports/report_generator.html", {"form": form})

@manager_or_above_required
def report_history_view(request):
    """История сгенерированных отчётов (заглушка)."""
    return render(request, "reports/report_list.html", {"reports": []})


@manager_or_above_required
def report_download(request, pk):
    """Скачивание ранее сгенерированного отчёта."""
    raise Http404("Отчёт не найден")


def _generate_excel_sync(report_type, date_from, date_to, counterparty=None):
    from .generators.excel import (
        generate_counterparty_card_excel,
        generate_debt_by_terms_excel,
        generate_overdue_registry_excel,
        generate_payment_calendar_excel,
        generate_procurement_structure_excel,
    )

    generators = {
        "overdue_registry": generate_overdue_registry_excel,
        "payment_calendar": generate_payment_calendar_excel,
        "procurement_structure": generate_procurement_structure_excel,
        "debt_by_terms": generate_debt_by_terms_excel,
        "counterparty_card": generate_counterparty_card_excel,
    }
    gen = generators.get(report_type)
    if not gen:
        raise ValueError(f"Неизвестный тип отчёта: {report_type}")
    return gen(date_from=date_from, date_to=date_to, counterparty=counterparty)
def _generate_pdf_sync(report_type, date_from, date_to, counterparty=None):
    from .generators.pdf import (
        generate_overdue_registry_pdf,
        generate_payment_calendar_pdf,
        generate_procurement_report_pdf,
    )

    generators = {
        "overdue_registry": generate_overdue_registry_pdf,
        "payment_calendar": generate_payment_calendar_pdf,
        "procurement_structure": generate_procurement_report_pdf,
    }
    gen = generators.get(report_type)
    if not gen:
        return _generate_excel_sync(report_type, date_from, date_to, counterparty)
    return gen(date_from=date_from, date_to=date_to, counterparty=counterparty)