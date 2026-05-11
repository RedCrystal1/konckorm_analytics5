from django.conf import settings
from django.db import models


class CashBalance(models.Model):
    """Прогнозный остаток денежных средств на дату."""

    date = models.DateField("Дата", unique=True, db_index=True)
    opening_balance = models.DecimalField(
        "Остаток на начало дня", max_digits=15, decimal_places=2
    )
    total_inflow = models.DecimalField(
        "Входящие платежи", max_digits=15, decimal_places=2, default=0
    )
    total_outflow = models.DecimalField(
        "Исходящие платежи", max_digits=15, decimal_places=2, default=0
    )
    closing_balance = models.DecimalField(
        "Остаток на конец дня", max_digits=15, decimal_places=2
    )
    is_cash_gap = models.BooleanField("Кассовый разрыв", default=False)
    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Прогнозный остаток"
        verbose_name_plural = "Прогнозные остатки"
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} | Остаток: {self.closing_balance}"


class CashGapAlert(models.Model):
    """Предупреждение о кассовом разрыве."""

    date = models.DateField("Дата кассового разрыва")
    deficit_amount = models.DecimalField(
        "Сумма дефицита", max_digits=15, decimal_places=2
    )
    contributing_payments = models.ManyToManyField(
        "registers.PlannedPayment",
        verbose_name="Платежи, вызывающие разрыв",
        blank=True,
    )
    is_acknowledged = models.BooleanField("Принято к сведению", default=False)
    acknowledged_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Предупреждение о кассовом разрыве"
        verbose_name_plural = "Предупреждения о кассовых разрывах"
        ordering = ["date"]

    def __str__(self):
        return f"Кассовый разрыв {self.date} | Дефицит: {self.deficit_amount}"


class PaymentRequest(models.Model):
    """Заявка на оплату — workflow «Менеджер → Бухгалтер → 1С».

    Жизненный цикл:
        draft       — черновик у менеджера, можно редактировать
        submitted   — отправлено бухгалтеру на согласование
        approved    — бухгалтер одобрил, готова к отправке в 1С
        rejected    — бухгалтер отклонил с комментарием → менеджеру
        sent_to_1c  — документ создан в 1С как черновик
        posted_in_1c — документ создан и проведён в 1С
        cancelled   — отменена менеджером

    После статуса sent_to_1c в поле one_c_doc_key хранится Ref_Key
    созданного в 1С платёжного поручения, что позволяет открыть
    его в 1С по прямой ссылке и предотвратить повторное создание.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        SUBMITTED = "submitted", "На согласовании"
        APPROVED = "approved", "Одобрено"
        REJECTED = "rejected", "Отклонено"
        SENT_TO_1C = "sent_to_1c", "Отправлено в 1С"
        POSTED_IN_1C = "posted_in_1c", "Проведено в 1С"
        CANCELLED = "cancelled", "Отменено"

    class Priority(models.TextChoices):
        HIGH = "high", "Высокий"
        MEDIUM = "medium", "Средний"
        LOW = "low", "Низкий"

    # ─── Кто и кому ───────────────────────────────────────
    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        on_delete=models.PROTECT,
        related_name="payment_requests",
        verbose_name="Поставщик",
    )
    contract = models.ForeignKey(
        "counterparties.Contract",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Договор",
    )
    related_receipt = models.ForeignKey(
        "documents.GoodsReceipt",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="payment_requests",
        verbose_name="Поступление-основание",
        help_text="Если заявка создана на оплату конкретной поставки",
    )

    # ─── Реквизиты платежа ────────────────────────────────
    amount = models.DecimalField(
        "Сумма к оплате", max_digits=15, decimal_places=2,
    )
    currency = models.CharField("Валюта", max_length=3, default="RUB")
    planned_date = models.DateField(
        "Планируемая дата платежа",
        help_text="Не должна быть в прошлом",
    )
    purpose = models.TextField(
        "Назначение платежа",
        help_text="Будет передано в 1С как назначение платежа",
    )
    priority = models.CharField(
        "Приоритет",
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )

    # ─── Состояние workflow ────────────────────────────────
    status = models.CharField(
        "Статус", max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    rejection_reason = models.TextField(
        "Причина отклонения", blank=True,
        help_text="Заполняется бухгалтером при отклонении",
    )

    # ─── Участники процесса ───────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payment_requests_created",
        verbose_name="Создал (менеджер)",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="payment_requests_reviewed",
        verbose_name="Проверил (бухгалтер)",
    )

    # ─── Интеграция с 1С ──────────────────────────────────
    one_c_doc_key = models.CharField(
        "Ref_Key документа в 1С", max_length=50, blank=True,
        help_text="GUID созданного в 1С платёжного поручения",
    )
    one_c_doc_number = models.CharField(
        "№ документа в 1С", max_length=30, blank=True,
    )
    sent_to_1c_at = models.DateTimeField(
        "Дата отправки в 1С", null=True, blank=True,
    )
    one_c_error = models.TextField(
        "Ошибка при отправке в 1С", blank=True,
    )

    # ─── Audit ────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Заявка на оплату"
        verbose_name_plural = "Заявки на оплату"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["counterparty", "-created_at"]),
        ]

    def __str__(self):
        return f"Заявка #{self.id} | {self.counterparty} | {self.amount} ₽"

    # ─── Бизнес-методы переходов состояний ────────────────

    @property
    def can_edit(self) -> bool:
        """Можно ли редактировать (только в черновике или после отклонения)."""
        return self.status in (self.Status.DRAFT, self.Status.REJECTED)

    @property
    def can_submit(self) -> bool:
        """Можно ли отправить на согласование."""
        return self.status in (self.Status.DRAFT, self.Status.REJECTED)

    @property
    def can_approve(self) -> bool:
        """Можно ли согласовать (только из 'на согласовании')."""
        return self.status == self.Status.SUBMITTED

    @property
    def can_reject(self) -> bool:
        return self.status == self.Status.SUBMITTED

    @property
    def can_send_to_1c(self) -> bool:
        """Можно ли отправить в 1С (только после согласования)."""
        return self.status == self.Status.APPROVED

    @property
    def can_cancel(self) -> bool:
        """Можно ли отменить (если ещё не в 1С)."""
        return self.status in (
            self.Status.DRAFT, self.Status.SUBMITTED,
            self.Status.APPROVED, self.Status.REJECTED,
        )

    @property
    def is_in_1c(self) -> bool:
        return self.status in (self.Status.SENT_TO_1C, self.Status.POSTED_IN_1C)

    @property
    def status_color(self) -> str:
        """CSS-переменная цвета по статусу (для шаблона)."""
        return {
            self.Status.DRAFT: "var(--text-3)",
            self.Status.SUBMITTED: "var(--info)",
            self.Status.APPROVED: "var(--accent)",
            self.Status.REJECTED: "var(--bad)",
            self.Status.SENT_TO_1C: "var(--ok)",
            self.Status.POSTED_IN_1C: "var(--ok)",
            self.Status.CANCELLED: "var(--text-3)",
        }.get(self.status, "var(--text-3)")


class PaymentRequestHistory(models.Model):
    """История изменений статуса заявки на оплату.

    Каждое действие записывается отдельной записью для аудита:
    кто, когда, какой переход совершил.
    """

    request = models.ForeignKey(
        PaymentRequest,
        on_delete=models.CASCADE,
        related_name="history",
    )
    from_status = models.CharField("Из статуса", max_length=20)
    to_status = models.CharField("В статус", max_length=20)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Запись истории заявки"
        verbose_name_plural = "История заявок"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} | {self.from_status} → {self.to_status}"
