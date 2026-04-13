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
