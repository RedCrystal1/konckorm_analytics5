import logging

from celery import shared_task

logger = logging.getLogger("apps.analytics")


@shared_task(name="apps.analytics.tasks.recalculate_all_kpi")
def recalculate_all_kpi():
    """Ежедневный пересчёт всех аналитических показателей."""
    from .services import recalculate_all_kpi as do_recalculate

    logger.info("Начат пересчёт KPI")
    snapshot = do_recalculate()
    logger.info(
        "KPI пересчитаны: долг=%.2f, просрочка=%.2f%%",
        snapshot.total_debt,
        snapshot.overdue_ratio,
    )
    return {
        "date": str(snapshot.date),
        "total_debt": str(snapshot.total_debt),
        "overdue_ratio": str(snapshot.overdue_ratio),
    }
