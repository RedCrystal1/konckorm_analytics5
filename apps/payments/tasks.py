import logging
from decimal import Decimal

from celery import shared_task

logger = logging.getLogger("apps.payments")


@shared_task(name="apps.payments.tasks.check_cash_gaps")
def check_cash_gaps():
    """Проверка кассовых разрывов на горизонт."""
    from .services import create_cash_gap_alerts, forecast_cash_balances

    logger.info("Начата проверка кассовых разрывов")

    # TODO: получить текущий остаток из AccountBalance или из настроек
    opening_balance = Decimal("0")

    gaps = forecast_cash_balances(opening_balance=opening_balance)

    if gaps:
        count = create_cash_gap_alerts(gaps)
        logger.warning("Обнаружено кассовых разрывов: %d", len(gaps))

        # Отправляем уведомления
        from apps.notifications.services import notify_cash_gaps

        notify_cash_gaps(gaps)
    else:
        logger.info("Кассовых разрывов не обнаружено")

    return {"gaps_found": len(gaps)}
