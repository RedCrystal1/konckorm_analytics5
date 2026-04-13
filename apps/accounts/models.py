import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Кастомная модель пользователя с ролями."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Администратор"
        ACCOUNTANT = "accountant", "Бухгалтер"
        MANAGER = "manager", "Руководитель"
        PROCUREMENT = "procurement", "Менеджер по закупкам"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(
        "Роль", max_length=20, choices=Role.choices, default=Role.ACCOUNTANT
    )
    patronymic = models.CharField("Отчество", max_length=150, blank=True)
    department = models.ForeignKey(
        "directories.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Подразделение",
        related_name="users",
    )
    phone = models.CharField("Телефон", max_length=20, blank=True)
    position = models.CharField("Должность", max_length=200, blank=True)
    is_two_factor_enabled = models.BooleanField("2FA включён", default=False)

    # Настройки уведомлений
    notify_overdue = models.BooleanField("Уведомлять о просрочке", default=True)
    notify_cash_gap = models.BooleanField(
        "Уведомлять о кассовых разрывах", default=True
    )
    notify_import = models.BooleanField(
        "Уведомлять о результатах импорта", default=False
    )

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.get_full_name() or self.username

    def get_full_name(self):
        parts = [self.last_name, self.first_name, self.patronymic]
        return " ".join(p for p in parts if p)

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    @property
    def is_accountant(self):
        return self.role == self.Role.ACCOUNTANT

    @property
    def is_manager(self):
        return self.role == self.Role.MANAGER

    @property
    def is_procurement(self):
        return self.role == self.Role.PROCUREMENT


class UserCounterpartyAccess(models.Model):
    """Привязка менеджеров по закупкам к «своим» контрагентам."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="counterparty_access"
    )
    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        on_delete=models.CASCADE,
        related_name="user_access",
    )

    class Meta:
        verbose_name = "Доступ к контрагенту"
        verbose_name_plural = "Доступ к контрагентам"
        unique_together = ["user", "counterparty"]

    def __str__(self):
        return f"{self.user} → {self.counterparty}"


class ActivityLog(models.Model):
    """Журнал активности пользователей (расширенный аудит)."""

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField("Действие", max_length=50)
    object_type = models.CharField("Тип объекта", max_length=100, blank=True)
    object_id = models.CharField("ID объекта", max_length=100, blank=True)
    object_repr = models.CharField("Описание объекта", max_length=500, blank=True)
    details = models.JSONField("Детали (было → стало)", default=dict, blank=True)
    ip_address = models.GenericIPAddressField("IP-адрес", null=True, blank=True)
    timestamp = models.DateTimeField("Время", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Запись журнала"
        verbose_name_plural = "Журнал аудита"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["object_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.user} — {self.action} — {self.timestamp}"
