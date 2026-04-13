from django.conf import settings
from django.db import models


class ImportSession(models.Model):
    """Сессия импорта данных."""

    class Mode(models.TextChoices):
        INITIAL = "initial", "Первоначальная загрузка"
        INCREMENTAL = "incremental", "Обновление (дельта)"
        ON_DEMAND = "on_demand", "Импорт по требованию"

    class Status(models.TextChoices):
        PENDING = "pending", "В очереди"
        PROCESSING = "processing", "Обработка"
        VALIDATING = "validating", "Валидация"
        COMPLETED = "completed", "Завершён"
        COMPLETED_WITH_WARNINGS = "completed_warnings", "Завершён с предупреждениями"
        FAILED = "failed", "Ошибка"

    class FileFormat(models.TextChoices):
        XML = "xml", "XML"
        EXCEL = "excel", "Excel"

    mode = models.CharField(
        "Режим импорта", max_length=20, choices=Mode.choices
    )
    status = models.CharField(
        "Статус", max_length=30, choices=Status.choices, default=Status.PENDING
    )
    file_format = models.CharField(
        "Формат файла", max_length=10, choices=FileFormat.choices
    )
    uploaded_file = models.FileField("Загруженный файл", upload_to="imports/%Y/%m/")

    # Статистика
    total_records = models.IntegerField("Всего записей", default=0)
    processed_records = models.IntegerField("Обработано", default=0)
    created_records = models.IntegerField("Создано", default=0)
    updated_records = models.IntegerField("Обновлено", default=0)
    error_records = models.IntegerField("Ошибок", default=0)
    checksum = models.CharField("Контрольная сумма", max_length=64, blank=True)

    # Дубли
    duplicates_found = models.IntegerField("Найдено дублей", default=0)

    started_at = models.DateTimeField("Начало", null=True, blank=True)
    completed_at = models.DateTimeField("Завершение", null=True, blank=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    error_message = models.TextField("Сообщение об ошибке", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Сессия импорта"
        verbose_name_plural = "Сессии импорта"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Импорт #{self.pk} ({self.get_status_display()})"

    @property
    def progress_percent(self):
        if self.total_records == 0:
            return 0
        return int(self.processed_records / self.total_records * 100)


class ImportLog(models.Model):
    """Детальный лог записей импорта."""

    class Level(models.TextChoices):
        INFO = "info", "Информация"
        WARNING = "warning", "Предупреждение"
        ERROR = "error", "Ошибка"

    session = models.ForeignKey(
        ImportSession, on_delete=models.CASCADE, related_name="logs"
    )
    level = models.CharField("Уровень", max_length=10, choices=Level.choices)
    message = models.TextField("Сообщение")
    row_number = models.IntegerField("Номер строки", null=True, blank=True)
    object_type = models.CharField("Тип объекта", max_length=100, blank=True)
    object_data = models.JSONField("Данные объекта", default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Запись лога импорта"
        verbose_name_plural = "Логи импорта"
        ordering = ["timestamp"]

    def __str__(self):
        return f"[{self.level}] Строка {self.row_number}: {self.message[:80]}"


class DuplicateCandidate(models.Model):
    """Кандидат на дублирование (найденный при импорте)."""

    class Resolution(models.TextChoices):
        PENDING = "pending", "Ожидает решения"
        MERGE = "merge", "Объединить"
        KEEP_BOTH = "keep_both", "Оставить оба"
        IGNORE = "ignore", "Игнорировать"

    session = models.ForeignKey(
        ImportSession, on_delete=models.CASCADE, related_name="duplicates"
    )
    existing_counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        on_delete=models.CASCADE,
        related_name="duplicate_existing",
    )
    new_counterparty_data = models.JSONField("Данные нового контрагента")
    match_field = models.CharField(
        "Поле совпадения",
        max_length=50,
        help_text="inn или name",
    )
    match_confidence = models.FloatField(
        "Уверенность совпадения",
        default=1.0,
        help_text="1.0 = точное совпадение ИНН, <1.0 = нечёткое совпадение имени",
    )
    resolution = models.CharField(
        "Решение",
        max_length=20,
        choices=Resolution.choices,
        default=Resolution.PENDING,
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Кандидат на дублирование"
        verbose_name_plural = "Кандидаты на дублирование"

    def __str__(self):
        return f"Дубль: {self.existing_counterparty} ({self.match_field})"
