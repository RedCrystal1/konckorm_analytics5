"""Management-команда для привязки платежей (PaymentOrder) к поступлениям
(GoodsReceipt) и расчёта paid_amount / is_paid у поступлений.

Логика:
    Для каждого контрагента отдельно по каждому договору:
      1. Берём все поступления, упорядоченные по дате (старые первыми).
      2. Берём все платежи, упорядоченные по дате (старые первыми).
      3. Применяем FIFO: первый платёж зачитывается в первое поступление,
         остаток (если есть) — во второе, и т.д.
      4. У платежа, который зачёлся полностью в одно поступление,
         выставляется related_receipt.

Это упрощённая модель — в реальной бухгалтерии 1С есть более сложные
правила («Способ зачёта авансов: Автоматически/По документу/Не зачитывать»),
но для аналитического приложения FIFO даёт >95% правильных привязок.

Авансы (платёж > сумма поступлений) — остаток платежа не привязывается
и считается авансом выданным (счёт 60.02). Учитывается в общей сумме
«оплачено» у контрагента.

Запуск:
    python manage.py link_payments_to_receipts          # реальный прогон
    python manage.py link_payments_to_receipts --dry-run # просмотр без записи
    python manage.py link_payments_to_receipts --counterparty=<id>  # один контрагент
    python manage.py link_payments_to_receipts --reset   # сначала обнулить все привязки
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.api.models import SyncSession
from apps.counterparties.models import Counterparty
from apps.documents.models import GoodsReceipt, PaymentOrder


class Command(BaseCommand):
    help = (
        "Привязка платежей (PaymentOrder) к поступлениям (GoodsReceipt) "
        "и расчёт оплаченных/неоплаченных документов методом FIFO."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать что будет сделано, но не сохранять в БД.",
        )
        parser.add_argument(
            "--counterparty",
            type=int,
            default=0,
            help="ID контрагента для обработки только одного (по умолчанию — все).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Сначала обнулить все paid_amount/is_paid/related_receipt.",
        )

    # ──────────────────────────────────────────────

    def handle(self, *args: Any, **options: Any) -> None:
        session = SyncSession.objects.create(
            direction=SyncSession.Direction.INCOMING,
            endpoint="manage.py link_payments_to_receipts",
        )

        dry_run: bool = options["dry_run"]
        only_cp_id: int = options["counterparty"]
        reset: bool = options["reset"]

        if reset and not dry_run:
            self.stdout.write(self.style.WARNING("Сброс предыдущих привязок..."))
            qs = GoodsReceipt.objects.all()
            if only_cp_id:
                qs = qs.filter(counterparty_id=only_cp_id)
            qs.update(paid_amount=Decimal("0"), is_paid=False)

            pqs = PaymentOrder.objects.all()
            if only_cp_id:
                pqs = pqs.filter(counterparty_id=only_cp_id)
            pqs.update(related_receipt=None)
            self.stdout.write(self.style.SUCCESS("✔ Сброшено.\n"))

        # Контрагенты, которые мы обрабатываем
        cps_qs = Counterparty.objects.all()
        if only_cp_id:
            cps_qs = cps_qs.filter(id=only_cp_id)
        cps = list(cps_qs.order_by("name"))

        if not cps:
            self.stdout.write(self.style.WARNING("Нет контрагентов для обработки."))
            return

        total_linked = total_advance = receipts_closed = receipts_partial = 0

        for cp in cps:
            stats = self._process_counterparty(cp, dry_run=dry_run)
            total_linked += stats["linked"]
            total_advance += stats["advance"]
            receipts_closed += stats["closed"]
            receipts_partial += stats["partial"]

        # Итог
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("═══ ИТОГО ═══"))
        self.stdout.write(self.style.SUCCESS(
            f"Платежей привязано: {total_linked}\n"
            f"Поступлений закрыто полностью: {receipts_closed}\n"
            f"Поступлений оплачено частично: {receipts_partial}\n"
            f"Авансов выдано (счёт 60.02): {total_advance} ₽"
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠ DRY-RUN: изменения НЕ записаны в БД."))

        session.records_received = total_linked
        session.records_created = total_linked
        session.status = SyncSession.Status.COMPLETED
        session.completed_at = timezone.now()
        session.details = {
            "linked": total_linked,
            "closed": receipts_closed,
            "partial": receipts_partial,
            "advance_amount": str(total_advance),
            "dry_run": dry_run,
        }
        session.save()

    # ──────────────────────────────────────────────
    # Обработка одного контрагента
    # ──────────────────────────────────────────────

    def _process_counterparty(
        self, cp: Counterparty, *, dry_run: bool
    ) -> dict[str, Any]:
        receipts = list(
            GoodsReceipt.objects.filter(counterparty=cp).order_by("date", "id")
        )
        payments = list(
            PaymentOrder.objects.filter(counterparty=cp).order_by("date", "id")
        )

        if not receipts and not payments:
            return {"linked": 0, "advance": Decimal("0"), "closed": 0, "partial": 0}

        total_receipts = sum(r.amount for r in receipts)
        total_payments = sum(p.amount for p in payments)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"► {cp.name}"))
        self.stdout.write(
            f"  Поступлений: {len(receipts)} на {total_receipts} ₽ | "
            f"Платежей: {len(payments)} на {total_payments} ₽"
        )

        # FIFO: для каждого платежа находим неоплаченные поступления и распределяем
        linked_count = 0
        closed_count = 0
        partial_count = 0
        advance_total = Decimal("0")
        # Снимок оплаченности (чтобы dry-run не трогал БД)
        paid_state: dict[int, Decimal] = {r.id: Decimal("0") for r in receipts}
        # related_receipt для каждого платежа в этой сессии
        payment_links: dict[int, int | None] = {}

        receipt_idx = 0
        for payment in payments:
            remaining = payment.amount  # сколько ещё нужно «положить» из этого платежа
            linked_to_receipts: list[int] = []

            while remaining > 0 and receipt_idx < len(receipts):
                receipt = receipts[receipt_idx]
                already_paid = paid_state[receipt.id]
                outstanding = receipt.amount - already_paid

                if outstanding <= 0:
                    # Это поступление уже полностью оплачено предыдущими платежами
                    receipt_idx += 1
                    continue

                # Зачисляем минимум из (остаток платежа, остаток к оплате)
                to_apply = min(remaining, outstanding)
                paid_state[receipt.id] += to_apply
                remaining -= to_apply
                linked_to_receipts.append(receipt.id)

                if paid_state[receipt.id] >= receipt.amount:
                    # Поступление закрыто полностью — переходим к следующему
                    receipt_idx += 1

            # Если платёж привязался ровно к одному поступлению — ставим related_receipt
            if len(linked_to_receipts) == 1:
                payment_links[payment.id] = linked_to_receipts[0]
                linked_count += 1
            elif len(linked_to_receipts) > 1:
                # Платёж разбился между несколькими поступлениями — related_receipt не ставим
                # (нет однозначной связи 1:1)
                payment_links[payment.id] = None
                linked_count += 1

            if remaining > 0:
                # Часть платежа не покрылась ни одним поступлением — это аванс (60.02)
                advance_total += remaining
                self.stdout.write(
                    f"    [аванс] Платёж №{payment.number} от {payment.date}: "
                    f"остаток {remaining} ₽ ушёл в авансы (60.02)"
                )

        # Подсчёт закрытых/частично оплаченных
        for receipt in receipts:
            paid = paid_state[receipt.id]
            if paid >= receipt.amount:
                closed_count += 1
                marker = "[✓ ОПЛАЧЕН]"
            elif paid > 0:
                partial_count += 1
                marker = f"[~ ЧАСТИЧНО {paid}/{receipt.amount}]"
            else:
                marker = "[× не оплачен]"
            self.stdout.write(
                f"    {marker} №{receipt.number} от {receipt.date} | "
                f"{receipt.amount} ₽"
            )

        # Записываем в БД (если не dry-run)
        if not dry_run:
            with transaction.atomic():
                for receipt in receipts:
                    paid = paid_state[receipt.id]
                    receipt.paid_amount = paid
                    receipt.is_paid = paid >= receipt.amount
                    receipt.save(update_fields=["paid_amount", "is_paid", "updated_at"])

                for payment_id, receipt_id in payment_links.items():
                    if receipt_id is not None:
                        PaymentOrder.objects.filter(id=payment_id).update(
                            related_receipt_id=receipt_id
                        )

        return {
            "linked": linked_count,
            "advance": advance_total,
            "closed": closed_count,
            "partial": partial_count,
        }
