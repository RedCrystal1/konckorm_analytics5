import logging

from celery import shared_task

logger = logging.getLogger("apps.data_import")


@shared_task(name="apps.data_import.tasks.process_import")
def process_import_task(session_id):
    """Фоновая обработка загруженного файла."""
    from .services import process_import

    logger.info("Начат фоновый импорт сессии #%d", session_id)
    process_import(session_id)

    # Уведомление пользователя
    from .models import ImportSession

    session = ImportSession.objects.get(pk=session_id)
    if session.initiated_by and session.initiated_by.notify_import:
        from apps.notifications.services import notify_import_complete

        notify_import_complete(session)

    return {"session_id": session_id, "status": session.status}
