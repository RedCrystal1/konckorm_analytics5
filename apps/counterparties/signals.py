import logging

from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger("apps.counterparties")


@receiver(pre_save, sender="counterparties.Counterparty")
def snapshot_before_change(sender, instance, **kwargs):
    """Автоматический снимок состояния контрагента перед каждым изменением.

    Позволяет видеть состояние справочника на любой момент времени
    для корректной ретроспективной аналитики.
    """
    if not instance.pk:
        return  # Новый объект, ещё нет чего снимать

    try:
        from .models import Counterparty, CounterpartyHistorySnapshot

        old = Counterparty.objects.get(pk=instance.pk)

        # Проверяем изменились ли ключевые поля
        tracked_fields = [
            "name", "full_name", "inn", "kpp", "legal_address", "actual_address",
            "phone", "email", "contact_person", "is_key_supplier", "is_active",
        ]
        changed = any(getattr(old, f) != getattr(instance, f) for f in tracked_fields)

        if not changed:
            return

        # Создаём снимок старого состояния
        data = {f: str(getattr(old, f, "")) for f in tracked_fields}
        data["_changed_fields"] = [
            f for f in tracked_fields if getattr(old, f) != getattr(instance, f)
        ]

        CounterpartyHistorySnapshot.objects.update_or_create(
            counterparty=old,
            snapshot_date=timezone.now().date(),
            defaults={"data": data},
        )

        logger.info(
            "Снимок контрагента %s: изменены поля %s",
            old.name,
            data["_changed_fields"],
        )

    except Counterparty.DoesNotExist:
        pass
    except Exception as e:
        logger.warning("Ошибка создания снимка контрагента: %s", e)
