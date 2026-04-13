import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin_test",
        password="adminpass123!",
        role=User.Role.ADMIN,
    )


@pytest.fixture
def accountant_user(db):
    return User.objects.create_user(
        username="acc_test",
        password="accpass123456",
        role=User.Role.ACCOUNTANT,
    )


@pytest.fixture
def procurement_user(db):
    return User.objects.create_user(
        username="proc_test",
        password="procpass12345",
        role=User.Role.PROCUREMENT,
    )


@pytest.mark.django_db
class TestLoginView:
    def test_login_page_loads(self):
        client = Client()
        response = client.get(reverse("accounts:login"))
        assert response.status_code == 200

    def test_login_success(self, admin_user):
        client = Client()
        response = client.post(
            reverse("accounts:login"),
            {"username": "admin_test", "password": "adminpass123!"},
        )
        assert response.status_code == 302

    def test_login_failure(self):
        client = Client()
        response = client.post(
            reverse("accounts:login"),
            {"username": "wrong", "password": "wrong"},
        )
        assert response.status_code == 200  # re-renders form


@pytest.mark.django_db
class TestUserListView:
    def test_admin_can_view(self, admin_user):
        client = Client()
        client.login(username="admin_test", password="adminpass123!")
        response = client.get(reverse("accounts:user_list"))
        assert response.status_code == 200

    def test_accountant_cannot_view(self, accountant_user):
        client = Client()
        client.login(username="acc_test", password="accpass123456")
        response = client.get(reverse("accounts:user_list"))
        assert response.status_code == 403

    def test_procurement_cannot_view(self, procurement_user):
        client = Client()
        client.login(username="proc_test", password="procpass12345")
        response = client.get(reverse("accounts:user_list"))
        assert response.status_code == 403


@pytest.mark.django_db
class TestProfileView:
    def test_profile_loads(self, accountant_user):
        client = Client()
        client.login(username="acc_test", password="accpass123456")
        response = client.get(reverse("accounts:profile"))
        assert response.status_code == 200

    def test_unauthenticated_redirect(self):
        client = Client()
        response = client.get(reverse("accounts:profile"))
        assert response.status_code == 302
