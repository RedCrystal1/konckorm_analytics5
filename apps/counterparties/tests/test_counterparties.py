import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.counterparties.models import Counterparty
from apps.counterparties.services import find_duplicates


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user(
        username="admin", password="adminpass123!", role=User.Role.ADMIN
    )
    client = Client()
    client.login(username="admin", password="adminpass123!")
    return client


@pytest.fixture
def sample_counterparty(db):
    return Counterparty.objects.create(
        name="ООО «Тест»",
        inn="7701234567",
        code_1c="TST-001",
        is_active=True,
    )


@pytest.mark.django_db
class TestCounterpartyModel:
    def test_str(self, sample_counterparty):
        assert "ООО «Тест»" in str(sample_counterparty)
        assert "7701234567" in str(sample_counterparty)

    def test_create_counterparty(self):
        cp = Counterparty.objects.create(
            name="Тест ИНН", inn="1234567890"
        )
        assert cp.pk is not None
        assert cp.is_active is True


@pytest.mark.django_db
class TestFindDuplicates:
    def test_find_by_inn(self, sample_counterparty):
        dupes = find_duplicates(inn="7701234567")
        assert len(dupes) == 1
        assert dupes[0]["match_field"] == "inn"
        assert dupes[0]["confidence"] == 1.0

    def test_no_duplicates(self):
        dupes = find_duplicates(inn="9999999999")
        assert len(dupes) == 0

    def test_find_by_name(self, sample_counterparty):
        dupes = find_duplicates(name="Тест")
        assert len(dupes) >= 1


@pytest.mark.django_db
class TestCounterpartyViews:
    def test_list_loads(self, admin_client):
        response = admin_client.get(reverse("counterparties:list"))
        assert response.status_code == 200

    def test_create_page_loads(self, admin_client):
        response = admin_client.get(reverse("counterparties:create"))
        assert response.status_code == 200

    def test_detail_loads(self, admin_client, sample_counterparty):
        response = admin_client.get(
            reverse("counterparties:detail", args=[sample_counterparty.pk])
        )
        assert response.status_code == 200
