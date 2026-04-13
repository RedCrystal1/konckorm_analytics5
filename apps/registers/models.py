from django.conf import settings
from django.db import models


class DebtByTerms(models.Model):
    """Регистр «Расчёты с поставщиками по срокам»."""

    class DebtStatus(models.TextChoices):
        CURRENT = "current", "Текущая"
        OVERDUE_30 = "overdue_30", "Просрочена до 30 дней"
        OVERDUE_60 = "overdue_60", "Просрочена 30–60 дней"
        OVERDUE_90 = "overdue_90", "Просрочена 60–90 дней"
        OVERDUE_90_PLUS = "overdue_90_plus", "Просрочена свыше 90 дней"
        DOUBTFUL = "doubtful", "Сомнительная"

    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        on_delete=models.CASCADE,
        related_name="debt_records",
    )
    contract = models.ForeignKey(
        "counterparties.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    source_document = models.ForeignKey(
        "documents.GoodsReceipt",
        on_delete=models.CASCADE,
        related_name="debt_records",
        verbose_name="Документ-основание",
    )
    planned_payment_date = models.DateField("Плановая дата оплаты")
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=DebtStatus.choices,
        default=DebtStatus.CURRENT,
    )
    responsible_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    amount_rub = models.DecimalField("Сумма (руб.)", max_digits=15, decimal_places=2)
    amount_currency = models.DecimalField(
        "Сумма в валюте договора",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    overdue_amount = models.DecimalField(
        "Сумма просрочки", max_digits=15, decimal_places=2, default=0
    )
    overdue_days = models.IntegerField("Дней просрочки", default=0)

    record_date = models.DateField("Дата записи", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Запись регистра задолженности"
        verbose_name_plural = "Регистр расчётов по срокам"
        indexes = [
            models.Index(fields=["status", "-record_date"]),
            models.Index(fields=["counterparty", "-record_date"]),
            models.Index(fields=["planned_payment_date"]),
        ]

    def __str__(self):
        return f"{self.counterparty} | {self.amount_rub} руб. | {self.get_status_display()}"


class ProcurementVolume(models.Model):
    """Регистр «Объёмы закупок по поставщикам»."""

    class PeriodType(models.TextChoices):
        MONTH = "month", "Месяц"
        QUARTER = "quarter", "Квартал"
        YEAR = "year", "Год"

    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        on_delete=models.CASCADE,
        related_name="procurement_volumes",
    )
    contract = models.ForeignKey(
        "counterparties.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    period_type = models.CharField(
        "Тип периода", max_length=10, choices=PeriodType.choices
    )
    period_start = models.DateField("Начало периода")
    period_end = models.DateField("Конец периода")
    procurement_kind = models.CharField(
        "Вид закупок",
        max_length=20,
        choices=[("raw", "Сырьё"), ("material", "Материалы"), ("service", "Услуги")],
        default="raw",
    )

    volume_rub = models.DecimalField(
        "Объём закупок (руб.)", max_digits=15, decimal_places=2
    )
    share_percent = models.DecimalField(
        "Доля в общем объёме (%)", max_digits=5, decimal_places=2, default=0
    )
    average_price = models.DecimalField(
        "Средняя цена закупки",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )

    calculated_at = models.DateTimeField("Дата расчёта", auto_now=True)

    class Meta:
        verbose_name = "Объём закупок"
        verbose_name_plural = "Регистр объёмов закупок"
        indexes = [
            models.Index(fields=["counterparty", "period_start"]),
        ]

    def __str__(self):
        return f"{self.counterparty} | {self.period_start} — {self.period_end} | {self.volume_rub}"


class PlannedPayment(models.Model):
    """Регистр «Плановые оплаты поставщикам»."""

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Ожидается"
        COMPLETED = "completed", "Исполнен"
        OVERDUE = "overdue", "Просрочен"
        CANCELLED = "cancelled", "Отменён"

    class Priority(models.TextChoices):
        HIGH = "high", "Высокий"
        MEDIUM = "medium", "Средний"
        LOW = "low", "Низкий"

    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        on_delete=models.CASCADE,
        related_name="planned_payments",
    )
    contract = models.ForeignKey(
        "counterparties.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    source_document = models.ForeignKey(
        "documents.GoodsReceipt",
        on_delete=models.CASCADE,
        related_name="planned_payments",
        verbose_name="Документ-основание",
    )
    planned_date = models.DateField("Плановая дата платежа", db_index=True)
    actual_date = models.DateField("Фактическая дата оплаты", null=True, blank=True)
    amount = models.DecimalField(
        "Сумма планового платежа", max_digits=15, decimal_places=2
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    priority = models.CharField(
        "Приоритет",
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    deviation_days = models.IntegerField("Отклонение (дни)", default=0)

    class Meta:
        verbose_name = "Плановый платёж"
        verbose_name_plural = "Регистр плановых платежей"
        ordering = ["planned_date"]
        indexes = [
            models.Index(fields=["planned_date", "status"]),
        ]

    def __str__(self):
        return f"{self.counterparty} | {self.planned_date} | {self.amount}"


class ContractConditionHistory(models.Model):
    """Регистр «История ставок и условий»."""

    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        on_delete=models.CASCADE,
    )
    contract = models.ForeignKey(
        "counterparties.Contract",
        on_delete=models.CASCADE,
    )
    valid_from = models.DateField("Действует с")
    valid_to = models.DateField("Действует по", null=True, blank=True)

    payment_term_type = models.CharField("Тип условий оплаты", max_length=20)
    payment_days = models.PositiveIntegerField("Срок оплаты (дней)")
    credit_limit = models.DecimalField(
        "Лимит кредитования",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    penalty_info = models.TextField("Штрафные санкции", blank=True)

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "История условий договора"
        verbose_name_plural = "Регистр истории условий"
        ordering = ["-valid_from"]

    def __str__(self):
        return f"{self.contract} | с {self.valid_from}"
