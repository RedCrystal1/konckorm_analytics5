import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User


@pytest.fixture
def manager_client(db):
    user = User.objects.create_user(
        username="rep_mgr", password="reppass123456", role=User.Role.MANAGER
    )
    client = Client()
    client.login(username="rep_mgr", password="reppass123456")
    return client


@pytest.mark.django_db
class TestReportViews:
    def test_generator_page(self, manager_client):
        response = manager_client.get(reverse("reports:generator"))
        assert response.status_code == 200

    def test_history_page(self, manager_client):
        response = manager_client.get(reverse("reports:history"))
        assert response.status_code == 200

    def test_procurement_cannot_access(self, db):
        User.objects.create_user(
            username="proc", password="procpass12345", role=User.Role.PROCUREMENT
        )
        client = Client()
        client.login(username="proc", password="procpass12345")
        response = client.get(reverse("reports:generator"))
        assert response.status_code == 403
