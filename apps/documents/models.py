from django.conf import settings
from django.db import models


class BaseDocument(models.Model):
    """Абстрактная базовая модель документа."""

    code_1c = models.CharField("Код в 1С", max_length=100, blank=True, null=True)
    number = models.CharField("Номер документа", max_length=100, db_index=True)
    date = models.DateField("Дата документа", db_index=True)
    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        on_delete=models.PROTECT,
        verbose_name="Контрагент",
    )
    contract = models.ForeignKey(
        "counterparties.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Договор",
    )
    amount = models.DecimalField("Сумма", max_digits=15, decimal_places=2)
    currency = models.CharField("Валюта", max_length=3, default="RUB")
    notes = models.TextField("Примечание", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_created",
    )

    class Meta:
        abstract = True
        ordering = ["-date", "-number"]


class GoodsReceipt(BaseDocument):
    """Поступление товаров и услуг (основание кредиторской задолженности)."""

    payment_due_date = models.DateField(
        "Срок оплаты",
        help_text="Может определяться автоматически из условий договора",
    )
    is_paid = models.BooleanField("Оплачен", default=False)
    paid_amount = models.DecimalField(
        "Оплаченная сумма", max_digits=15, decimal_places=2, default=0
    )

    class Meta(BaseDocument.Meta):
        verbose_name = "Поступление товаров и услуг"
        verbose_name_plural = "Поступления товаров и услуг"

    def __str__(self):
        return f"Поступление №{self.number} от {self.date}"

    @property
    def outstanding_amount(self):
        """Остаток к оплате."""
        return self.amount - self.paid_amount

    @property
    def overdue_days(self):
        """Количество дней просрочки."""
        from django.utils import timezone

        if self.is_paid or not self.payment_due_date:
            return 0
        delta = timezone.now().date() - self.payment_due_date
        return max(0, delta.days)


class GoodsReceiptItem(models.Model):
    """Строка документа поступления (товарная позиция)."""

    receipt = models.ForeignKey(
        GoodsReceipt, on_delete=models.CASCADE, related_name="items"
    )
    nomenclature = models.ForeignKey(
        "directories.Nomenclature",
        on_delete=models.PROTECT,
        verbose_name="Номенклатура",
    )
    quantity = models.DecimalField("Количество", max_digits=15, decimal_places=3)
    price = models.DecimalField("Цена", max_digits=15, decimal_places=2)
    amount = models.DecimalField("Сумма", max_digits=15, decimal_places=2)
    vat_rate = models.DecimalField(
        "Ставка НДС (%)", max_digits=5, decimal_places=2, default=20
    )
    vat_amount = models.DecimalField(
        "Сумма НДС", max_digits=15, decimal_places=2, default=0
    )

    class Meta:
        verbose_name = "Строка поступления"
        verbose_name_plural = "Строки поступления"


class PaymentOrder(BaseDocument):
    """Платёжное поручение исходящее (факт оплаты)."""

    payment_purpose = models.TextField("Назначение платежа", blank=True)
    related_receipt = models.ForeignKey(
        GoodsReceipt,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name="Связанное поступление",
    )

    class Meta(BaseDocument.Meta):
        verbose_name = "Платёжное поручение"
        verbose_name_plural = "Платёжные поручения"

    def __str__(self):
        return f"Платёжное поручение №{self.number} от {self.date}"


class Invoice(BaseDocument):
    """Счёт на оплату."""

    class Direction(models.TextChoices):
        INCOMING = "incoming", "Входящий"
        OUTGOING = "outgoing", "Исходящий"

    direction = models.CharField(
        "Направление",
        max_length=10,
        choices=Direction.choices,
        default=Direction.INCOMING,
    )
    payment_due_date = models.DateField("Срок оплаты", null=True, blank=True)
    is_paid = models.BooleanField("Оплачен", default=False)

    class Meta(BaseDocument.Meta):
        verbose_name = "Счёт на оплату"
        verbose_name_plural = "Счета на оплату"

    def __str__(self):
        return f"Счёт №{self.number} от {self.date}"


class AccountBalance(models.Model):
    """Остатки по счетам бухгалтерского учёта на дату."""

    class AccountCode(models.TextChoices):
        ACC_60_01 = "60.01", "60.01 Расчёты с поставщиками"
        ACC_60_02 = "60.02", "60.02 Авансы выданные"
        ACC_60_21 = "60.21", "60.21 Расчёты в условных единицах"
        ACC_62 = "62", "62 Расчёты с покупателями"
        ACC_76 = "76", "76 Расчёты с разными дебиторами и кредиторами"

    account = models.CharField("Счёт", max_length=10, choices=AccountCode.choices)
    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        on_delete=models.CASCADE,
        related_name="balances",
    )
    contract = models.ForeignKey(
        "counterparties.Contract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    balance_date = models.DateField("Дата остатка", db_index=True)
    debit = models.DecimalField("Дебет", max_digits=15, decimal_places=2, default=0)
    credit = models.DecimalField("Кредит", max_digits=15, decimal_places=2, default=0)
    balance = models.DecimalField("Сальдо", max_digits=15, decimal_places=2, default=0)

    class Meta:
        verbose_name = "Остаток по счёту"
        verbose_name_plural = "Остатки по счетам"
        ordering = ["-balance_date"]
        indexes = [
            models.Index(fields=["account", "counterparty", "-balance_date"]),
        ]

    def __str__(self):
        return f"{self.account} | {self.counterparty} | {self.balance_date}"
