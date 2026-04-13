import pytest
from datetime import date, timedelta
from decimal import Decimal

from apps.accounts.models import User
from apps.analytics.calculators import (
    calculate_overdue_ratio,
    calculate_total_debt,
)
from apps.counterparties.models import Counterparty
from apps.documents.models import GoodsReceipt


@pytest.fixture
def setup_data(db):
    cp = Counterparty.objects.create(name="Тест", inn="1234567890")

    # Unpaid receipt
    GoodsReceipt.objects.create(
        number="T001",
        date=date.today() - timedelta(days=30),
        counterparty=cp,
        amount=Decimal("100000"),
        paid_amount=Decimal("0"),
        payment_due_date=date.today() - timedelta(days=10),
    )

    # Paid receipt
    GoodsReceipt.objects.create(
        number="T002",
        date=date.today() - timedelta(days=20),
        counterparty=cp,
        amount=Decimal("50000"),
        paid_amount=Decimal("50000"),
        payment_due_date=date.today(),
        is_paid=True,
    )

    return cp


@pytest.mark.django_db
class TestCalculators:
    def test_total_debt(self, setup_data):
        debt = calculate_total_debt()
        assert debt == Decimal("100000")

    def test_overdue_ratio_zero_debt(self):
        ratio = calculate_overdue_ratio(Decimal("0"), Decimal("0"))
        assert ratio == Decimal("0")

    def test_overdue_ratio_calculation(self):
        ratio = calculate_overdue_ratio(Decimal("100000"), Decimal("25000"))
        assert ratio == Decimal("25.00")
