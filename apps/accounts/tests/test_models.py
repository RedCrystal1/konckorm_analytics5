import pytest
from django.test import TestCase

from apps.accounts.models import ActivityLog, User


@pytest.mark.django_db
class TestUserModel:
    def test_create_user(self):
        user = User.objects.create_user(
            username="testuser",
            password="testpass123!",
            first_name="Иван",
            last_name="Петров",
            patronymic="Сергеевич",
            role=User.Role.ACCOUNTANT,
        )
        assert str(user) == "Петров Иван Сергеевич"
        assert user.is_accountant is True
        assert user.is_admin is False

    def test_role_properties(self):
        admin = User(role=User.Role.ADMIN)
        assert admin.is_admin is True
        assert admin.is_accountant is False

        mgr = User(role=User.Role.MANAGER)
        assert mgr.is_manager is True

        proc = User(role=User.Role.PROCUREMENT)
        assert proc.is_procurement is True

    def test_get_full_name_with_patronymic(self):
        user = User(last_name="Иванов", first_name="Пётр", patronymic="Сергеевич")
        assert user.get_full_name() == "Иванов Пётр Сергеевич"

    def test_get_full_name_without_patronymic(self):
        user = User(last_name="Иванов", first_name="Пётр")
        assert user.get_full_name() == "Иванов Пётр"

    def test_str_fallback_to_username(self):
        user = User(username="testuser")
        assert str(user) == "testuser"


@pytest.mark.django_db
class TestActivityLog:
    def test_create_log(self):
        user = User.objects.create_user(username="loguser", password="pass123456")
        log = ActivityLog.objects.create(
            user=user,
            action="login",
            ip_address="127.0.0.1",
        )
        assert log.action == "login"
        assert log.ip_address == "127.0.0.1"
        assert "login" in str(log)
