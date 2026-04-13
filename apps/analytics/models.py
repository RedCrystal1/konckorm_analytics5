from django.db import models


class AnalyticsSnapshot(models.Model):
    """Снимок рассчитанных аналитических показателей за период."""

    date = models.DateField("Дата расчёта", db_index=True)

    # KPI
    total_debt = models.DecimalField(
        "Общая сумма КЗ", max_digits=15, decimal_places=2
    )
    overdue_debt = models.DecimalField(
        "Просроченная КЗ", max_digits=15, decimal_places=2
    )
    overdue_ratio = models.DecimalField(
        "Доля просроченной КЗ (%)", max_digits=5, decimal_places=2
    )
    turnover_days = models.DecimalField(
        "Оборачиваемость КЗ (дни)", max_digits=7, decimal_places=1
    )
    payment_ratio = models.DecimalField(
        "Коэффициент погашения", max_digits=5, decimal_places=3
    )
    avg_payment_days = models.DecimalField(
        "Средний срок оплаты (дни)", max_digits=7, decimal_places=1
    )
    avg_deviation_days = models.DecimalField(
        "Среднее отклонение от договорных сроков (дни)",
        max_digits=7,
        decimal_places=1,
    )
    key_supplier_share = models.DecimalField(
        "Доля ключевых поставщиков (%)", max_digits=5, decimal_places=2
    )

    # Прогнозы
    forecast_cash_need_week = models.DecimalField(
        "Прогноз потребности (неделя)",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    forecast_cash_need_month = models.DecimalField(
        "Прогноз потребности (месяц)",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    cash_gap_probability = models.DecimalField(
        "Вероятность кассового разрыва (%)",
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
    )

    calculated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Аналитический снимок"
        verbose_name_plural = "Аналитические снимки"
        ordering = ["-date"]
        get_latest_by = "date"

    def __str__(self):
        return f"Аналитика за {self.date}"
