from django.conf import settings
from django.db import models


class GeneratedReport(models.Model):
    REPORT_TYPES = [
        ("overdue_registry", "Реестр просроченной задолженности"),
        ("payment_calendar", "Платёжный календарь"),
        ("procurement_structure", "Структура закупок"),
        ("debt_by_terms", "Задолженность по срокам"),
        ("counterparty_card", "Карточка контрагента"),
    ]
    OUTPUT_FORMATS = [("excel", "Excel"), ("pdf", "PDF")]

    report_type = models.CharField("Тип отчёта", max_length=32, choices=REPORT_TYPES)
    output_format = models.CharField("Формат", max_length=8, choices=OUTPUT_FORMATS)
    date_from = models.DateField("Дата с", null=True, blank=True)
    date_to = models.DateField("Дата по", null=True, blank=True)
    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Контрагент",
    )
    file = models.FileField("Файл", upload_to="reports/%Y/%m/")
    file_size = models.PositiveIntegerField("Размер файла (байт)", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Сформировал",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Сгенерированный отчёт"
        verbose_name_plural = "История отчётов"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_report_type_display()} ({self.created_at:%d.%m.%Y %H:%M})"

    @property
    def filename(self):
        import os
        return os.path.basename(self.file.name) if self.file else ""