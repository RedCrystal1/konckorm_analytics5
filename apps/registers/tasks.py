import logging
from datetime import date, timedelta

from celery import shared_task
from dateutil.relativedelta import relativedelta

logger = logging.getLogger("apps.registers")


@shared_task(name="apps.registers.tasks.update_debt_by_terms")
def update_debt_by_terms():
    """Ежедневное обновление регистра задолженности по срокам."""
    from .services import update_debt_statuses, update_planned_payments

    logger.info("Начат пересчёт регистра задолженности по срокам")
    count = update_debt_statuses()
    update_planned_payments()
    logger.info("Пересчёт завершён: %d записей обновлено", count)
    return count


@shared_task(name="apps.registers.tasks.update_procurement_volumes")
def update_procurement_volumes():
    """Ежемесячный расчёт объёмов закупок за прошедший месяц."""
    from .services import calculate_procurement_volumes

    today = date.today()
    period_end = today.replace(day=1) - timedelta(days=1)
    period_start = period_end.replace(day=1)

    logger.info("Расчёт объёмов закупок за %s — %s", period_start, period_end)
    count = calculate_procurement_volumes(period_start, period_end, period_type="month")
    return count
