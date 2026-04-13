import pytest
from datetime import date, timedelta
from decimal import Decimal

from apps.counterparties.models import Counterparty
from apps.documents.models import GoodsReceipt


@pytest.fixture
def counterparty(db):
    return Counterparty.objects.create(name="Тест", inn="1234567890")


@pytest.mark.django_db
class TestGoodsReceipt:
    def test_outstanding_amount(self, counterparty):
        receipt = GoodsReceipt.objects.create(
            number="001",
            date=date.today(),
            counterparty=counterparty,
            amount=Decimal("100000"),
            paid_amount=Decimal("30000"),
            payment_due_date=date.today(),
        )
        assert receipt.outstanding_amount == Decimal("70000")

    def test_overdue_days_paid(self, counterparty):
        receipt = GoodsReceipt.objects.create(
            number="002",
            date=date.today() - timedelta(days=60),
            counterparty=counterparty,
            amount=Decimal("50000"),
            payment_due_date=date.today() - timedelta(days=30),
            is_paid=True,
        )
        assert receipt.overdue_days == 0

    def test_overdue_days_unpaid(self, counterparty):
        receipt = GoodsReceipt.objects.create(
            number="003",
            date=date.today() - timedelta(days=60),
            counterparty=counterparty,
            amount=Decimal("50000"),
            payment_due_date=date.today() - timedelta(days=15),
        )
        assert receipt.overdue_days == 15

    def test_overdue_days_not_yet_due(self, counterparty):
        receipt = GoodsReceipt.objects.create(
            number="004",
            date=date.today(),
            counterparty=counterparty,
            amount=Decimal("50000"),
            payment_due_date=date.today() + timedelta(days=10),
        )
        assert receipt.overdue_days == 0
