from django.conf import settings
from django.db import models


class Counterparty(models.Model):
    """Контрагент (поставщик/подрядчик)."""

    code_1c = models.CharField(
        "Код в 1С",
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        help_text="Уникальный идентификатор из учётной системы 1С",
    )
    name = models.CharField("Наименование", max_length=500, db_index=True)
    full_name = models.CharField("Полное наименование", max_length=1000, blank=True)
    inn = models.CharField("ИНН", max_length=12, db_index=True)
    kpp = models.CharField("КПП", max_length=9, blank=True)
    legal_address = models.TextField("Юридический адрес", blank=True)
    actual_address = models.TextField("Фактический адрес", blank=True)
    phone = models.CharField("Телефон", max_length=100, blank=True)
    email = models.EmailField("Email", blank=True)
    contact_person = models.CharField("Контактное лицо", max_length=300, blank=True)

    is_key_supplier = models.BooleanField(
        "Ключевой поставщик",
        default=False,
        help_text="Поставщик, обеспечивающий 80% закупок",
    )
    is_active = models.BooleanField("Активен", default=True)

    responsible_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_counterparties",
        verbose_name="Ответственный менеджер",
    )

    notes = models.TextField("Примечания", blank=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    class Meta:
        verbose_name = "Контрагент"
        verbose_name_plural = "Контрагенты"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["inn"]),
            models.Index(fields=["is_key_supplier"]),
        ]

    def __str__(self):
        return f"{self.name} (ИНН: {self.inn})"


class CounterpartyHistorySnapshot(models.Model):
    """Снимок справочника контрагента на дату (для ретроспективной аналитики)."""

    counterparty = models.ForeignKey(
        Counterparty, on_delete=models.CASCADE, related_name="history_snapshots"
    )
    snapshot_date = models.DateField("Дата снимка")
    data = models.JSONField("Данные на дату")
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Снимок контрагента"
        verbose_name_plural = "Снимки контрагентов"
        ordering = ["-snapshot_date"]
        unique_together = ["counterparty", "snapshot_date"]


class Contract(models.Model):
    """Договор с контрагентом."""

    class Kind(models.TextChoices):
        SUPPLY = "supply", "Поставка"
        SERVICE = "service", "Оказание услуг"
        WORK = "work", "Подряд"
        LEASE = "lease", "Аренда"
        OTHER = "other", "Прочее"

    class Currency(models.TextChoices):
        RUB = "RUB", "Российский рубль"
        USD = "USD", "Доллар США"
        EUR = "EUR", "Евро"
        CU = "CU", "Условные единицы"

    class PaymentTermType(models.TextChoices):
        PREPAYMENT = "prepayment", "Предоплата"
        DEFERRED = "deferred", "Отсрочка платежа"
        ON_DELIVERY = "on_delivery", "По факту поставки"
        MIXED = "mixed", "Смешанная"

    code_1c = models.CharField("Код в 1С", max_length=50, blank=True, null=True)
    counterparty = models.ForeignKey(
        Counterparty,
        on_delete=models.CASCADE,
        related_name="contracts",
        verbose_name="Контрагент",
    )
    number = models.CharField("Номер договора", max_length=100)
    name = models.CharField("Наименование", max_length=500, blank=True)
    date = models.DateField("Дата заключения")
    kind = models.CharField(
        "Вид договора", max_length=20, choices=Kind.choices, default=Kind.SUPPLY
    )
    currency = models.CharField(
        "Валюта", max_length=3, choices=Currency.choices, default=Currency.RUB
    )

    # Условия оплаты
    payment_term_type = models.CharField(
        "Тип условий оплаты",
        max_length=20,
        choices=PaymentTermType.choices,
        default=PaymentTermType.DEFERRED,
    )
    payment_days = models.PositiveIntegerField(
        "Срок оплаты (дней)",
        default=30,
        help_text="Количество дней на оплату от даты документа",
    )
    credit_limit = models.DecimalField(
        "Лимит кредитования",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
    )
    penalty_rate = models.DecimalField(
        "Ставка штрафных санкций (%)",
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    valid_from = models.DateField("Действует с", null=True, blank=True)
    valid_to = models.DateField("Действует по", null=True, blank=True)
    is_active = models.BooleanField("Действующий", default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Договор"
        verbose_name_plural = "Договоры"
        ordering = ["-date"]

    def __str__(self):
        return f"Договор №{self.number} от {self.date} ({self.counterparty.name})"
