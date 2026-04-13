import pytest
from datetime import date, timedelta
from decimal import Decimal

from apps.counterparties.models import Counterparty
from apps.documents.models import GoodsReceipt
from apps.registers.models import DebtByTerms
from apps.registers.services import update_debt_statuses


@pytest.fixture
def setup_receipts(db):
    cp = Counterparty.objects.create(name="Тест", inn="1234567890")

    # Current (not yet due)
    GoodsReceipt.objects.create(
        number="R001", date=date.today(), counterparty=cp,
        amount=Decimal("50000"), payment_due_date=date.today() + timedelta(days=10),
    )

    # Overdue 15 days
    GoodsReceipt.objects.create(
        number="R002", date=date.today() - timedelta(days=45), counterparty=cp,
        amount=Decimal("80000"), payment_due_date=date.today() - timedelta(days=15),
    )

    # Overdue 45 days
    GoodsReceipt.objects.create(
        number="R003", date=date.today() - timedelta(days=75), counterparty=cp,
        amount=Decimal("120000"), payment_due_date=date.today() - timedelta(days=45),
    )

    # Paid (should be excluded)
    GoodsReceipt.objects.create(
        number="R004", date=date.today() - timedelta(days=60), counterparty=cp,
        amount=Decimal("30000"), paid_amount=Decimal("30000"),
        payment_due_date=date.today() - timedelta(days=30), is_paid=True,
    )

    return cp


@pytest.mark.django_db
class TestUpdateDebtStatuses:
    def test_creates_records(self, setup_receipts):
        count = update_debt_statuses()
        assert count == 3  # 3 unpaid receipts

    def test_correct_statuses(self, setup_receipts):
        update_debt_statuses()
        records = DebtByTerms.objects.all()

        statuses = {r.source_document.number: r.status for r in records}
        assert statuses["R001"] == DebtByTerms.DebtStatus.CURRENT
        assert statuses["R002"] == DebtByTerms.DebtStatus.OVERDUE_30
        assert statuses["R003"] == DebtByTerms.DebtStatus.OVERDUE_60

    def test_paid_receipts_excluded(self, setup_receipts):
        update_debt_statuses()
        assert not DebtByTerms.objects.filter(
            source_document__number="R004"
        ).exists()
