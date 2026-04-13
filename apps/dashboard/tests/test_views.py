import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User


@pytest.fixture
def auth_client(db):
    user = User.objects.create_user(
        username="dash_user", password="dashpass12345", role=User.Role.ACCOUNTANT
    )
    client = Client()
    client.login(username="dash_user", password="dashpass12345")
    return client


@pytest.mark.django_db
class TestDashboardView:
    def test_dashboard_loads(self, auth_client):
        response = auth_client.get(reverse("dashboard:index"))
        assert response.status_code == 200

    def test_dashboard_requires_auth(self):
        client = Client()
        response = client.get(reverse("dashboard:index"))
        assert response.status_code == 302

    def test_htmx_kpi_cards(self, auth_client):
        response = auth_client.get(reverse("dashboard:htmx_kpi_cards"))
        assert response.status_code == 200

    def test_htmx_overdue_table(self, auth_client):
        response = auth_client.get(reverse("dashboard:htmx_overdue_table"))
        assert response.status_code == 200
