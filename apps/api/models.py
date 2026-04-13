from django.conf import settings
from django.db import models
import uuid


class APIToken(models.Model):
    """Токен доступа к API для внешних систем (1С)."""

    key = models.CharField("Ключ", max_length=64, unique=True, default="")
    name = models.CharField("Название системы", max_length=200)
    is_active = models.BooleanField("Активен", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
    )
    permissions = models.JSONField(
        "Разрешения",
        default=dict,
        blank=True,
        help_text='{"read": true, "write": true, "sync_back": true}',
    )
    last_used_at = models.DateTimeField("Последнее использование", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "API-токен"
        verbose_name_plural = "API-токены"

    def __str__(self):
        return f"{self.name} ({'активен' if self.is_active else 'отключён'})"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = uuid.uuid4().hex + uuid.uuid4().hex[:32]
        super().save(*args, **kwargs)


class SyncSession(models.Model):
    """Сессия синхронизации с внешней системой."""

    class Direction(models.TextChoices):
        INCOMING = "incoming", "Из 1С в платформу"
        OUTGOING = "outgoing", "Из платформы в 1С"

    class Status(models.TextChoices):
        STARTED = "started", "Начата"
        COMPLETED = "completed", "Завершена"
        FAILED = "failed", "Ошибка"

    direction = models.CharField("Направление", max_length=10, choices=Direction.choices)
    status = models.CharField("Статус", max_length=10, choices=Status.choices, default=Status.STARTED)
    api_token = models.ForeignKey(APIToken, on_delete=models.SET_NULL, null=True, blank=True)

    endpoint = models.CharField("Эндпоинт", max_length=200)
    records_received = models.IntegerField("Получено записей", default=0)
    records_created = models.IntegerField("Создано", default=0)
    records_updated = models.IntegerField("Обновлено", default=0)
    records_errors = models.IntegerField("Ошибок", default=0)
    error_message = models.TextField("Сообщение об ошибке", blank=True)
    details = models.JSONField("Детали", default=dict, blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Сессия синхронизации"
        verbose_name_plural = "Сессии синхронизации"
        ordering = ["-started_at"]

    def __str__(self):
        return f"Синхр. {self.get_direction_display()} — {self.get_status_display()} ({self.started_at})"
