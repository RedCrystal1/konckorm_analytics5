from django.conf import settings
from django.db import models


class ReconciliationAct(models.Model):
    """Акт сверки взаиморасчётов."""

    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        on_delete=models.CASCADE,
        related_name="reconciliation_acts",
    )
    period_start = models.DateField("Начало периода сверки")
    period_end = models.DateField("Конец периода сверки")
    our_balance = models.DecimalField(
        "Наше сальдо", max_digits=15, decimal_places=2
    )
    their_balance = models.DecimalField(
        "Сальдо контрагента",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    is_matched = models.BooleanField("Данные совпали", default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Акт сверки"
        verbose_name_plural = "Акты сверки"
        ordering = ["-period_end"]

    def __str__(self):
        return f"Сверка {self.counterparty} за {self.period_start} — {self.period_end}"


class Discrepancy(models.Model):
    """Расхождение при сверке."""

    class Status(models.TextChoices):
        OPEN = "open", "Открыто"
        IN_PROGRESS = "in_progress", "В работе"
        RESOLVED = "resolved", "Закрыто"

    class Reason(models.TextChoices):
        MISSING_DOC = "missing_doc", "Отсутствует документ"
        AMOUNT_MISMATCH = "amount_mismatch", "Расхождение в сумме"
        DATE_MISMATCH = "date_mismatch", "Расхождение в дате"
        DUPLICATE = "duplicate", "Дублирование"
        OTHER = "other", "Иное"

    reconciliation_act = models.ForeignKey(
        ReconciliationAct,
        on_delete=models.CASCADE,
        related_name="discrepancies",
    )
    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        on_delete=models.CASCADE,
    )
    document_ref = models.CharField("Документ расхождения", max_length=200)
    our_amount = models.DecimalField(
        "Сумма по нашим данным", max_digits=15, decimal_places=2
    )
    their_amount = models.DecimalField(
        "Сумма по данным контрагента",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    discrepancy_amount = models.DecimalField(
        "Сумма расхождения", max_digits=15, decimal_places=2
    )
    reason = models.CharField(
        "Причина",
        max_length=20,
        choices=Reason.choices,
        default=Reason.OTHER,
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    resolution_comment = models.TextField(
        "Комментарий по урегулированию", blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField("Дата закрытия", null=True, blank=True)

    class Meta:
        verbose_name = "Расхождение"
        verbose_name_plural = "Расхождения при сверке"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.document_ref} | {self.discrepancy_amount} | {self.get_status_display()}"
