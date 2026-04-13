import pytest

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.notifications.services import create_notification


@pytest.mark.django_db
class TestNotifications:
    def test_create_notification(self):
        user = User.objects.create_user(username="ntest", password="pass1234567")
        notif = create_notification(
            user=user,
            type_=Notification.Type.SYSTEM,
            title="Тест",
            message="Тестовое уведомление",
            severity="info",
        )
        assert notif.pk is not None
        assert notif.is_read is False
        assert notif.user == user

    def test_notification_str(self):
        user = User.objects.create_user(username="ntest2", password="pass1234567")
        notif = create_notification(
            user=user,
            type_=Notification.Type.OVERDUE,
            title="Просрочка!",
            message="Тест",
            severity="warning",
        )
        assert "Просрочка!" in str(notif)
