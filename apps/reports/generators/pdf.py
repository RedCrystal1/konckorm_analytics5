import io
import logging
from datetime import date

logger = logging.getLogger("apps.reports")


def generate_overdue_registry_pdf(date_from=None, date_to=None, counterparty=None):
    """PDF: реестр просроченной задолженности."""
    from apps.registers.models import DebtByTerms

    qs = DebtByTerms.objects.exclude(
        status=DebtByTerms.DebtStatus.CURRENT
    ).select_related("counterparty", "source_document").order_by("-overdue_days")

    if date_from:
        qs = qs.filter(planned_payment_date__gte=date_from)
    if date_to:
        qs = qs.filter(planned_payment_date__lte=date_to)
    if counterparty:
        qs = qs.filter(counterparty=counterparty)

    title = f"Реестр просроченной задолженности на {date.today().strftime('%d.%m.%Y')}"
    headers = ["Контрагент", "Документ", "Срок оплаты", "Сумма", "Просрочка", "Дней"]
    col_widths = [55, 40, 28, 30, 30, 18]

    rows = []
    for r in qs:
        rows.append([
            r.counterparty.name[:30],
            str(r.source_document.number),
            r.planned_payment_date.strftime("%d.%m.%Y"),
            f"{r.amount_rub:,.0f}",
            f"{r.overdue_amount:,.0f}",
            str(r.overdue_days),
        ])

    return _build_pdf(title, headers, col_widths, rows)


def generate_payment_calendar_pdf(date_from=None, date_to=None, counterparty=None):
    """PDF: платёжный календарь."""
    from apps.registers.models import PlannedPayment

    qs = PlannedPayment.objects.select_related(
        "counterparty", "contract"
    ).order_by("planned_date")

    if date_from:
        qs = qs.filter(planned_date__gte=date_from)
    if date_to:
        qs = qs.filter(planned_date__lte=date_to)
    if counterparty:
        qs = qs.filter(counterparty=counterparty)

    title = "Платёжный календарь"
    headers = ["Дата", "Контрагент", "Договор", "Сумма", "Приоритет", "Статус"]
    col_widths = [25, 50, 35, 30, 25, 25]

    rows = []
    for p in qs:
        rows.append([
            p.planned_date.strftime("%d.%m.%Y"),
            p.counterparty.name[:28],
            str(p.contract or "—")[:20],
            f"{p.amount:,.0f}",
            p.get_priority_display(),
            p.get_status_display(),
        ])

    return _build_pdf(title, headers, col_widths, rows)


def generate_procurement_report_pdf(date_from=None, date_to=None, counterparty=None):
    """PDF: структура закупок."""
    from apps.registers.models import ProcurementVolume

    qs = ProcurementVolume.objects.select_related("counterparty").order_by("-volume_rub")

    if date_from:
        qs = qs.filter(period_start__gte=date_from)
    if date_to:
        qs = qs.filter(period_end__lte=date_to)
    if counterparty:
        qs = qs.filter(counterparty=counterparty)

    title = "Структура закупок по поставщикам"
    headers = ["Поставщик", "Период", "Вид", "Объём (руб.)", "Доля (%)"]
    col_widths = [50, 40, 30, 35, 20]

    rows = []
    for v in qs:
        rows.append([
            v.counterparty.name[:28],
            f"{v.period_start.strftime('%d.%m.%Y')}—{v.period_end.strftime('%d.%m.%Y')}",
            v.get_procurement_kind_display(),
            f"{v.volume_rub:,.0f}",
            f"{v.share_percent:.1f}%",
        ])

    return _build_pdf(title, headers, col_widths, rows)


def _build_pdf(title, headers, col_widths, rows):
    """Универсальный генератор PDF-таблицы через fpdf2."""
    from fpdf import FPDF

    # Подключаем шрифт с поддержкой кириллицы
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)

    # Пробуем подключить DejaVu (поддерживает кириллицу)
    font_loaded = False
    import os
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            font_name = "CustomFont"
            pdf.add_font(font_name, "", fp, uni=True)
            pdf.add_font(font_name, "B", fp.replace("Sans.", "Sans-Bold.").replace("arial.", "arialbd."), uni=True)
            font_loaded = True
            break

    if not font_loaded:
        # Fallback: встроенный шрифт (без кириллицы, но не упадёт)
        font_name = "Helvetica"

    pdf.add_page()

    # Заголовок
    pdf.set_font(font_name, "B", 14)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(3)

    # Дата формирования
    pdf.set_font(font_name, "", 8)
    pdf.cell(0, 5, f"Дата формирования: {date.today().strftime('%d.%m.%Y')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Шапка таблицы
    pdf.set_font(font_name, "B", 8)
    pdf.set_fill_color(44, 90, 160)
    pdf.set_text_color(255, 255, 255)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, h, border=1, fill=True, align="C")
    pdf.ln()

    # Данные
    pdf.set_font(font_name, "", 7)
    pdf.set_text_color(0, 0, 0)
    fill = False
    for row in rows:
        if pdf.get_y() > 185:  # Переход на новую страницу
            pdf.add_page()
            pdf.set_font(font_name, "B", 8)
            pdf.set_fill_color(44, 90, 160)
            pdf.set_text_color(255, 255, 255)
            for w, h in zip(col_widths, headers):
                pdf.cell(w, 7, h, border=1, fill=True, align="C")
            pdf.ln()
            pdf.set_font(font_name, "", 7)
            pdf.set_text_color(0, 0, 0)

        if fill:
            pdf.set_fill_color(240, 244, 248)
        else:
            pdf.set_fill_color(255, 255, 255)

        for w, val in zip(col_widths, row):
            pdf.cell(w, 6, str(val), border=1, fill=True)
        pdf.ln()
        fill = not fill

    # Итого
    pdf.ln(3)
    pdf.set_font(font_name, "B", 9)
    pdf.cell(0, 6, f"Всего записей: {len(rows)}", new_x="LMARGIN", new_y="NEXT")

    buf = io.BytesIO()
    pdf.output(buf)
    buf.seek(0)
    return buf