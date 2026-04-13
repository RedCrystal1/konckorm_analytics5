from django.conf import settings
from django.db import models


class Notification(models.Model):
    """Уведомление пользователя."""

    class Type(models.TextChoices):
        OVERDUE = "overdue", "Просрочка платежа"
        CASH_GAP = "cash_gap", "Кассовый разрыв"
        IMPORT_COMPLETE = "import_complete", "Импорт завершён"
        IMPORT_ERROR = "import_error", "Ошибка импорта"
        DISCREPANCY = "discrepancy", "Новое расхождение при сверке"
        SYSTEM = "system", "Системное уведомление"

    class Severity(models.TextChoices):
        INFO = "info", "Информация"
        WARNING = "warning", "Предупреждение"
        CRITICAL = "critical", "Критическое"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField("Тип", max_length=20, choices=Type.choices)
    severity = models.CharField(
        "Важность",
        max_length=10,
        choices=Severity.choices,
        default=Severity.INFO,
    )
    title = models.CharField("Заголовок", max_length=300)
    message = models.TextField("Сообщение")
    link = models.CharField(
        "Ссылка",
        max_length=500,
        blank=True,
        help_text="URL для перехода при клике",
    )
    is_read = models.BooleanField("Прочитано", default=False)
    is_email_sent = models.BooleanField("Email отправлен", default=False)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField("Прочитано в", null=True, blank=True)

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.get_severity_display()}] {self.title}"
