import logging

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger("apps.notifications")


@shared_task(name="apps.notifications.tasks.send_overdue_alerts")
def send_overdue_alerts():
    """Ежедневная рассылка уведомлений о просрочке и скором наступлении срока."""
    from .services import notify_overdue_payments, notify_upcoming_payments

    count = notify_overdue_payments()
    count += notify_upcoming_payments()
    logger.info("Отправлено уведомлений: %d", count)
    return count


@shared_task(name="apps.notifications.tasks.send_email_notification")
def send_email_notification(notification_id):
    """Отправка email-уведомления."""
    from .models import Notification

    try:
        notification = Notification.objects.select_related("user").get(pk=notification_id)

        if notification.is_email_sent:
            return

        if not notification.user.email:
            logger.warning(
                "У пользователя %s нет email", notification.user
            )
            return

        send_mail(
            subject=notification.title,
            message=notification.message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[notification.user.email],
            fail_silently=False,
        )

        notification.is_email_sent = True
        notification.save(update_fields=["is_email_sent"])

        logger.info("Email отправлен: %s → %s", notification.title, notification.user.email)

    except Notification.DoesNotExist:
        logger.error("Уведомление #%d не найдено", notification_id)
    except Exception as e:
        logger.exception("Ошибка отправки email для уведомления #%d: %s", notification_id, e)
