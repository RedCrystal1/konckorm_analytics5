"""Management-команда для реконструкции остатков счёта 60.01/60.02
на основе имеющихся в БД документов (поступлений и платежей).

В стандартной бухгалтерии 1С счёт 60 формируется именно из этих документов,
поэтому "наша" реконструкция функционально эквивалентна тому, что показал бы
регистр бухгалтерии 1С. Это позволяет:
  * не зависеть от особенностей OData 1С (которые не отдают субконто в проводках);
  * иметь актуальные остатки на любую дату — пересчёт занимает доли секунды;
  * выполнять сверку «расчётное сальдо ↔ сальдо в 1С» когда 1С будет доступна.

Логика по счетам:

  60.01 (Пассивный — мы должны поставщикам)
    Кт-оборот = сумма поступлений за период (увеличение долга)
    Дт-оборот = сумма платежей в счёт оплаты поставок (погашение долга)
    Сальдо Кт на дату = (Кт-оборот накопительно) − (Дт-оборот накопительно), если > 0

  60.02 (Активный — нам должны поставщики, авансы)
    Дт-оборот = сумма платежей-авансов (когда мы заплатили больше, чем поступило)
    Кт-оборот = сумма зачёта авансов (когда пришло поступление, закрытое авансом)
    Сальдо Дт на дату = (Дт-оборот) − (Кт-оборот), если > 0

В упрощённой модели, реализованной в этом проекте:
  * для каждого платежа определяется сколько из него ушло в 60.01 (оплата)
    и сколько в 60.02 (аванс) — это уже сделано командой link_payments_to_receipts;
  * сальдо считается как разница между Кт- и Дт-оборотом, накопительно
    по дате документов.

Запуск:
    python manage.py recalc_account_60                # на конец каждого дня где были движения
    python manage.py recalc_account_60 --daily         # на каждый день в диапазоне (плотный график)
    python manage.py recalc_account_60 --counterparty=3  # один контрагент
    python manage.py recalc_account_60 --reset         # сначала удалить старые AccountBalance
"""
from __future__ import annotations

import datetime as _dt
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Min, Max
from django.utils import timezone

from apps.api.models import SyncSession
from apps.counterparties.models import Counterparty
from apps.documents.models import AccountBalance, GoodsReceipt, PaymentOrder

ACC_60_01 = AccountBalance.AccountCode.ACC_60_01  # "60.01"
ACC_60_02 = AccountBalance.AccountCode.ACC_60_02  # "60.02"


class Command(BaseCommand):
    help = (
        "Расчёт остатков счетов 60.01/60.02 для каждого контрагента "
        "на основе документов поступлений и платежей."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--daily",
            action="store_true",
            help="Считать остаток на КАЖДЫЙ день в диапазоне (плотный график). "
                 "По умолчанию — только на даты движений (компактнее).",
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
            help="Перед расчётом удалить все существующие AccountBalance.",
        )
        parser.add_argument(
            "--from",
            dest="date_from",
            default="",
            help="Начало периода в ISO (YYYY-MM-DD). По умолчанию — самая ранняя дата.",
        )
        parser.add_argument(
            "--to",
            dest="date_to",
            default="",
            help="Конец периода в ISO (YYYY-MM-DD). По умолчанию — сегодня.",
        )

    # ──────────────────────────────────────────────

    def handle(self, *args: Any, **options: Any) -> None:
        session = SyncSession.objects.create(
            direction=SyncSession.Direction.INCOMING,
            endpoint="manage.py recalc_account_60",
        )

        daily: bool = options["daily"]
        only_cp_id: int = options["counterparty"]
        reset: bool = options["reset"]
        date_from = _parse_date(options["date_from"])
        date_to = _parse_date(options["date_to"]) or timezone.now().date()

        cps_qs = Counterparty.objects.all()
        if only_cp_id:
            cps_qs = cps_qs.filter(id=only_cp_id)

        if reset:
            self.stdout.write(self.style.WARNING("Удаляю существующие AccountBalance..."))
            ab_qs = AccountBalance.objects.all()
            if only_cp_id:
                ab_qs = ab_qs.filter(counterparty_id=only_cp_id)
            deleted, _ = ab_qs.delete()
            self.stdout.write(self.style.SUCCESS(f"✔ Удалено: {deleted}\n"))

        total_balances = 0
        cps = list(cps_qs.order_by("name"))

        for cp in cps:
            n = self._process_counterparty(
                cp, date_from=date_from, date_to=date_to, daily=daily
            )
            total_balances += n

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("═══ ИТОГО ═══"))
        self.stdout.write(self.style.SUCCESS(
            f"Контрагентов обработано: {len(cps)}\n"
            f"Записей AccountBalance: {total_balances}"
        ))

        session.records_received = total_balances
        session.records_created = total_balances
        session.status = SyncSession.Status.COMPLETED
        session.completed_at = timezone.now()
        session.details = {
            "balances": total_balances,
            "daily": daily,
            "date_from": str(date_from) if date_from else None,
            "date_to": str(date_to),
        }
        session.save()

    # ──────────────────────────────────────────────

    def _process_counterparty(
        self, cp: Counterparty, *,
        date_from: _dt.date | None,
        date_to: _dt.date,
        daily: bool,
    ) -> int:
        receipts = list(
            GoodsReceipt.objects.filter(counterparty=cp).order_by("date", "id")
        )
        payments = list(
            PaymentOrder.objects.filter(counterparty=cp).order_by("date", "id")
        )

        if not receipts and not payments:
            return 0

        # Определяем диапазон дат
        all_dates = [r.date for r in receipts] + [p.date for p in payments]
        period_start = date_from or min(all_dates)
        period_end = date_to

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"► {cp.name}"))

        # Список дат, на которые считаем сальдо
        if daily:
            dates_to_calc = _date_range(period_start, period_end)
        else:
            # Только даты движений (компактнее)
            movement_dates = sorted(set(all_dates))
            # +1 финальная дата на сегодня (если последнее движение давно)
            if movement_dates and movement_dates[-1] != period_end:
                movement_dates.append(period_end)
            dates_to_calc = movement_dates

        # Готовим словари быстрого доступа: дата → список документов
        receipts_by_date: dict[_dt.date, list[GoodsReceipt]] = {}
        for r in receipts:
            receipts_by_date.setdefault(r.date, []).append(r)

        payments_by_date: dict[_dt.date, list[PaymentOrder]] = {}
        for p in payments:
            payments_by_date.setdefault(p.date, []).append(p)

        # Накопительные обороты по 60.01 и 60.02
        # 60.01 (мы должны): Кт = поступления, Дт = платежи в счёт оплаты
        # 60.02 (авансы):    Дт = платежи-авансы, Кт = зачёт аванса при поступлении
        cum_60_01_credit = Decimal("0")  # все поступления накопительно
        cum_60_01_debit = Decimal("0")   # все «оплачивающие» платежи
        cum_60_02_debit = Decimal("0")   # все «авансовые» платежи
        cum_60_02_credit = Decimal("0")  # зачёт авансов при поступлениях

        # Сначала «прокрутим» все документы хронологически и распределим их на счета
        # с учётом того, что аванс на дату поступления превращается в зачёт.
        # Для простоты: каждый платёж считаем «оплата уже существующих поступлений»;
        # излишек идёт в авансы.
        timeline: list[tuple[_dt.date, str, Decimal]] = []
        for r in receipts:
            timeline.append((r.date, "receipt", r.amount))
        for p in payments:
            timeline.append((p.date, "payment", p.amount))
        timeline.sort(key=lambda t: t[0])

        # Имитация распределения платежей по поступлениям (FIFO на лету)
        outstanding_receipts: list[Decimal] = []  # неоплаченные остатки поступлений в порядке прихода
        movements: list[tuple[_dt.date, str, str, Decimal]] = []
        # (date, account, dr_or_cr, amount)

        for d, kind, amount in timeline:
            if kind == "receipt":
                outstanding_receipts.append(amount)
                # 60.01 Кт = поступление пришло
                movements.append((d, "60.01", "Cr", amount))
                # Одновременно: если до этого был аванс — он зачитывается
                advance_to_apply = min(cum_60_02_debit - cum_60_02_credit, amount)
                if advance_to_apply > 0:
                    # 60.01 Дт = погашение долга авансом
                    movements.append((d, "60.01", "Dr", advance_to_apply))
                    # 60.02 Кт = зачёт аванса
                    movements.append((d, "60.02", "Cr", advance_to_apply))
                    cum_60_02_credit += advance_to_apply
                    # Уменьшаем outstanding на сумму зачёта
                    self._reduce_outstanding(outstanding_receipts, advance_to_apply)
            else:  # payment
                # Платёж: FIFO по неоплаченным поступлениям
                remaining = amount
                idx = 0
                applied_to_60_01 = Decimal("0")
                while remaining > 0 and idx < len(outstanding_receipts):
                    available = outstanding_receipts[idx]
                    if available <= 0:
                        idx += 1
                        continue
                    take = min(remaining, available)
                    outstanding_receipts[idx] = available - take
                    remaining -= take
                    applied_to_60_01 += take
                    if outstanding_receipts[idx] == 0:
                        idx += 1
                # То что пошло в счёт поступлений → 60.01 Дт
                if applied_to_60_01 > 0:
                    movements.append((d, "60.01", "Dr", applied_to_60_01))
                # Что не нашло поступление → 60.02 Дт (аванс)
                if remaining > 0:
                    movements.append((d, "60.02", "Dr", remaining))
                    cum_60_02_debit += remaining

        # Теперь по каждой дате из dates_to_calc считаем сальдо
        cnt = 0
        with transaction.atomic():
            for snap_date in dates_to_calc:
                # Накопительные обороты до snap_date включительно
                dr_60_01 = sum(
                    m[3] for m in movements
                    if m[0] <= snap_date and m[1] == "60.01" and m[2] == "Dr"
                )
                cr_60_01 = sum(
                    m[3] for m in movements
                    if m[0] <= snap_date and m[1] == "60.01" and m[2] == "Cr"
                )
                dr_60_02 = sum(
                    m[3] for m in movements
                    if m[0] <= snap_date and m[1] == "60.02" and m[2] == "Dr"
                )
                cr_60_02 = sum(
                    m[3] for m in movements
                    if m[0] <= snap_date and m[1] == "60.02" and m[2] == "Cr"
                )

                bal_60_01 = cr_60_01 - dr_60_01  # положительное = мы должны
                bal_60_02 = dr_60_02 - cr_60_02  # положительное = нам должны (аванс)

                # 60.01
                if cr_60_01 or dr_60_01:
                    AccountBalance.objects.update_or_create(
                        account="60.01", counterparty=cp, contract=None,
                        balance_date=snap_date,
                        defaults={
                            "debit": dr_60_01,
                            "credit": cr_60_01,
                            "balance": bal_60_01,
                        },
                    )
                    cnt += 1

                # 60.02
                if cr_60_02 or dr_60_02:
                    AccountBalance.objects.update_or_create(
                        account="60.02", counterparty=cp, contract=None,
                        balance_date=snap_date,
                        defaults={
                            "debit": dr_60_02,
                            "credit": cr_60_02,
                            "balance": bal_60_02,
                        },
                    )
                    cnt += 1

        # Финальные цифры на последнюю дату
        if dates_to_calc:
            last_date = dates_to_calc[-1]
            last_60_01 = AccountBalance.objects.filter(
                counterparty=cp, account="60.01", balance_date__lte=last_date
            ).order_by("-balance_date").first()
            last_60_02 = AccountBalance.objects.filter(
                counterparty=cp, account="60.02", balance_date__lte=last_date
            ).order_by("-balance_date").first()
            self.stdout.write(
                f"  60.01: Кт {(last_60_01.credit if last_60_01 else 0):>10} ₽ | "
                f"Дт {(last_60_01.debit if last_60_01 else 0):>10} ₽ | "
                f"Сальдо: {(last_60_01.balance if last_60_01 else 0):>10} ₽"
            )
            self.stdout.write(
                f"  60.02: Дт {(last_60_02.debit if last_60_02 else 0):>10} ₽ | "
                f"Кт {(last_60_02.credit if last_60_02 else 0):>10} ₽ | "
                f"Сальдо: {(last_60_02.balance if last_60_02 else 0):>10} ₽ (аванс)"
            )

        return cnt

    def _reduce_outstanding(self, outstanding: list[Decimal], amount: Decimal) -> None:
        """Уменьшить неоплаченные остатки FIFO на сумму amount."""
        remaining = amount
        for i, val in enumerate(outstanding):
            if remaining <= 0:
                break
            if val <= 0:
                continue
            take = min(remaining, val)
            outstanding[i] = val - take
            remaining -= take


def _parse_date(s: str) -> _dt.date | None:
    if not s:
        return None
    try:
        return _dt.date.fromisoformat(s)
    except ValueError:
        return None


def _date_range(start: _dt.date, end: _dt.date) -> list[_dt.date]:
    return [start + _dt.timedelta(days=i) for i in range((end - start).days + 1)]
