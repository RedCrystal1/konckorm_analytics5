import pytest
from datetime import date
from decimal import Decimal
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.payments.models import CashBalance, CashGapAlert


@pytest.fixture
def manager_client(db):
    user = User.objects.create_user(
        username="pay_mgr", password="paypass123456", role=User.Role.MANAGER
    )
    client = Client()
    client.login(username="pay_mgr", password="paypass123456")
    return client


@pytest.mark.django_db
class TestCashBalanceModel:
    def test_create(self):
        cb = CashBalance.objects.create(
            date=date.today(),
            opening_balance=Decimal("1000000"),
            total_outflow=Decimal("300000"),
            closing_balance=Decimal("700000"),
        )
        assert cb.is_cash_gap is False

    def test_cash_gap(self):
        cb = CashBalance.objects.create(
            date=date.today(),
            opening_balance=Decimal("100000"),
            total_outflow=Decimal("500000"),
            closing_balance=Decimal("-400000"),
            is_cash_gap=True,
        )
        assert cb.is_cash_gap is True


@pytest.mark.django_db
class TestPaymentViews:
    def test_calendar_loads(self, manager_client):
        response = manager_client.get(reverse("payments:calendar"))
        assert response.status_code == 200

    def test_alerts_loads(self, manager_client):
        response = manager_client.get(reverse("payments:alerts"))
        assert response.status_code == 200

    def test_procurement_cannot_access(self, db):
        User.objects.create_user(
            username="proc", password="procpass12345", role=User.Role.PROCUREMENT
        )
        client = Client()
        client.login(username="proc", password="procpass12345")
        response = client.get(reverse("payments:calendar"))
        assert response.status_code == 403
