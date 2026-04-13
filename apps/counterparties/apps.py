from django.apps import AppConfig


class CounterpartiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.counterparties"
    verbose_name = "Контрагенты"

    def ready(self):
        import apps.counterparties.signals  # noqa: F401
