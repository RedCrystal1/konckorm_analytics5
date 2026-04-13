from django.db import models


class Department(models.Model):
    """Подразделение предприятия."""

    name = models.CharField("Наименование", max_length=300)
    code = models.CharField("Код", max_length=50, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Родительское подразделение",
    )
    is_active = models.BooleanField("Активно", default=True)

    class Meta:
        verbose_name = "Подразделение"
        verbose_name_plural = "Подразделения"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Nomenclature(models.Model):
    """Номенклатура (закупаемые товары, сырьё, материалы, услуги)."""

    class Kind(models.TextChoices):
        RAW_MATERIAL = "raw", "Сырьё"
        MATERIAL = "material", "Материалы"
        SERVICE = "service", "Услуги"
        GOODS = "goods", "Товары"
        OTHER = "other", "Прочее"

    name = models.CharField("Наименование", max_length=500)
    code = models.CharField("Код", max_length=50, unique=True)
    kind = models.CharField(
        "Вид", max_length=20, choices=Kind.choices, default=Kind.OTHER
    )
    unit = models.CharField("Единица измерения", max_length=50, blank=True)
    is_active = models.BooleanField("Активно", default=True)

    class Meta:
        verbose_name = "Номенклатура"
        verbose_name_plural = "Номенклатура"
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} — {self.name}"
