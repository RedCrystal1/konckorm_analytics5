import logging

from celery import shared_task

logger = logging.getLogger("apps.reports")


@shared_task(name="apps.reports.tasks.generate_report_async")
def generate_report_async(report_type, output_format, params=None):
    """Фоновая генерация тяжёлого отчёта."""
    from datetime import datetime

    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    params = params or {}
    date_from = params.get("date_from")
    date_to = params.get("date_to")

    if date_from:
        date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
    if date_to:
        date_to = datetime.strptime(date_to, "%Y-%m-%d").date()

    logger.info("Генерация отчёта: %s (%s)", report_type, output_format)

    if output_format == "excel":
        buf = _generate_excel(report_type, date_from, date_to)
        ext = "xlsx"
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        buf = _generate_pdf(report_type, date_from, date_to)
        ext = "pdf"
        content_type = "application/pdf"

    # Сохраняем файл
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reports/{report_type}_{timestamp}.{ext}"
    path = default_storage.save(filename, ContentFile(buf.read()))

    logger.info("Отчёт сохранён: %s", path)
    return {"path": path, "content_type": content_type}


def _generate_excel(report_type, date_from, date_to):
    from .generators.excel import (
        generate_overdue_registry_excel,
        generate_payment_calendar_excel,
        generate_procurement_structure_excel,
    )

    generators = {
        "overdue_registry": generate_overdue_registry_excel,
        "payment_calendar": generate_payment_calendar_excel,
        "procurement_structure": generate_procurement_structure_excel,
    }
    gen = generators.get(report_type)
    if not gen:
        raise ValueError(f"Неизвестный тип отчёта: {report_type}")
    return gen(date_from=date_from, date_to=date_to)


def _generate_pdf(report_type, date_from, date_to):
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
        raise ValueError(f"Неизвестный тип отчёта: {report_type}")
    return gen(date_from=date_from, date_to=date_to)
