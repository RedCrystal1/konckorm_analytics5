import pytest
from datetime import date
from decimal import Decimal

from apps.accounts.models import User
from apps.counterparties.models import Counterparty
from apps.reconciliation.models import Discrepancy, ReconciliationAct
from apps.reconciliation.services import resolve_discrepancy


@pytest.fixture
def counterparty(db):
    return Counterparty.objects.create(name="Тест Сверка", inn="1112223334")


@pytest.fixture
def act(counterparty, db):
    return ReconciliationAct.objects.create(
        counterparty=counterparty,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 3, 31),
        our_balance=Decimal("500000"),
    )


@pytest.mark.django_db
class TestReconciliation:
    def test_create_discrepancy(self, act, counterparty):
        disc = Discrepancy.objects.create(
            reconciliation_act=act,
            counterparty=counterparty,
            document_ref="ПТУ-001",
            our_amount=Decimal("100000"),
            their_amount=Decimal("95000"),
            discrepancy_amount=Decimal("5000"),
            reason=Discrepancy.Reason.AMOUNT_MISMATCH,
        )
        assert disc.status == Discrepancy.Status.OPEN
        assert disc.discrepancy_amount == Decimal("5000")

    def test_resolve_discrepancy(self, act, counterparty):
        disc = Discrepancy.objects.create(
            reconciliation_act=act,
            counterparty=counterparty,
            document_ref="ПТУ-002",
            our_amount=Decimal("50000"),
            their_amount=Decimal("50000"),
            discrepancy_amount=Decimal("0"),
        )
        resolved = resolve_discrepancy(
            disc,
            status=Discrepancy.Status.RESOLVED,
            comment="Совпадение подтверждено",
        )
        assert resolved.status == Discrepancy.Status.RESOLVED
        assert resolved.resolved_at is not None
