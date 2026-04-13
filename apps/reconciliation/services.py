import logging
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.documents.models import GoodsReceipt, PaymentOrder

from .models import Discrepancy, ReconciliationAct

logger = logging.getLogger("apps.reconciliation")


def generate_reconciliation_act(counterparty, period_start, period_end, user=None):
    """Формирование акта сверки с автоматическим созданием расхождений и уведомлений."""

    # Наши данные: поступления (кредит) минус оплаты (дебет)
    receipts_total = (
        GoodsReceipt.objects.filter(
            counterparty=counterparty,
            date__gte=period_start,
            date__lte=period_end,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    payments_total = (
        PaymentOrder.objects.filter(
            counterparty=counterparty,
            date__gte=period_start,
            date__lte=period_end,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0")
    )

    our_balance = receipts_total - payments_total

    act, created = ReconciliationAct.objects.update_or_create(
        counterparty=counterparty,
        period_start=period_start,
        period_end=period_end,
        defaults={
            "our_balance": our_balance,
            "created_by": user,
        },
    )

    logger.info(
        "Сформирован акт сверки для %s (ИНН: %s) за %s — %s: сальдо %s",
        counterparty.name, counterparty.inn, period_start, period_end, our_balance,
    )

    # ── Автоматическое создание расхождений ──
    # По каждому неоплаченному документу за период создаём расхождение
    unmatched_receipts = GoodsReceipt.objects.filter(
        counterparty=counterparty,
        date__gte=period_start,
        date__lte=period_end,
        is_paid=False,
    )

    discrepancies_created = 0
    for receipt in unmatched_receipts:
        outstanding = receipt.outstanding_amount
        if outstanding > 0:
            disc, disc_created = Discrepancy.objects.get_or_create(
                reconciliation_act=act,
                counterparty=counterparty,
                document_ref=f"Поступление №{receipt.number} от {receipt.date.strftime('%d.%m.%Y')}",
                defaults={
                    "our_amount": receipt.amount,
                    "their_amount": None,
                    "discrepancy_amount": outstanding,
                    "reason": Discrepancy.Reason.AMOUNT_MISMATCH,
                    "status": Discrepancy.Status.OPEN,
                    "responsible": user,
                },
            )
            if disc_created:
                discrepancies_created += 1

                # ── Уведомление о расхождении ──
                try:
                    from apps.accounts.models import User
                    from apps.notifications.models import Notification
                    from apps.notifications.services import create_notification

                    for admin_user in User.objects.filter(role__in=["admin", "accountant"], is_active=True):
                        create_notification(
                            user=admin_user,
                            type_=Notification.Type.DISCREPANCY,
                            title=f"Расхождение: {counterparty.name}",
                            message=(
                                f"Контрагент: {counterparty.name} (ИНН: {counterparty.inn})\n"
                                f"Документ: {disc.document_ref}\n"
                                f"Сумма расхождения: {disc.discrepancy_amount:,.0f} руб.\n"
                                f"Причина: {disc.get_reason_display()}"
                            ),
                            severity="warning",
                            link=f"/reconciliation/{disc.pk}/",
                        )
                except Exception as e:
                    logger.warning("Не удалось отправить уведомление о расхождении: %s", e)

    # Обновляем статус совпадения
    if discrepancies_created > 0:
        act.is_matched = False
    else:
        act.is_matched = True
    act.save()

    logger.info("  Создано расхождений: %d", discrepancies_created)

    return act


def check_reconciliation_match(act, their_balance):
    """Проверка совпадения данных акта сверки."""
    act.their_balance = their_balance
    act.is_matched = act.our_balance == their_balance
    act.save(update_fields=["their_balance", "is_matched"])

    if not act.is_matched:
        discrepancy_amount = act.our_balance - their_balance
        Discrepancy.objects.create(
            reconciliation_act=act,
            counterparty=act.counterparty,
            document_ref=f"Акт сверки за {act.period_start} — {act.period_end}",
            our_amount=act.our_balance,
            their_amount=their_balance,
            discrepancy_amount=abs(discrepancy_amount),
            reason=Discrepancy.Reason.AMOUNT_MISMATCH,
        )

    return act.is_matched


def resolve_discrepancy(discrepancy, status, comment="", user=None):
    """Закрытие расхождения."""
    discrepancy.status = status
    discrepancy.resolution_comment = comment
    discrepancy.responsible = user
    if status == Discrepancy.Status.RESOLVED:
        discrepancy.resolved_at = timezone.now()
    discrepancy.save()
    return discrepancy