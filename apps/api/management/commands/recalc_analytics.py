"""Management-команда для синхронного пересчёта аналитических регистров
после импорта данных или привязки платежей.

Полезна когда:
  * Только что закончился sync_from_1c и нужно обновить сводки.
  * После link_payments_to_receipts: поступления стали оплаченными,
    а DebtByTerms их ещё «помнит» как долг.
  * Перед демонстрацией приложения, чтобы все цифры были актуальные.

В продакшене эту работу делает Celery-задача update_debt_by_terms
по расписанию (раз в сутки). Команда даёт способ дёрнуть её вручную
без поднятия Celery worker'а.

Запуск:
    python manage.py recalc_analytics
    python manage.py recalc_analytics --debt-only       # только DebtByTerms
    python manage.py recalc_analytics --snapshots-only  # только AnalyticsSnapshot
"""
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Пересчёт регистров задолженности и аналитических снапшотов."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--debt-only",
            action="store_true",
            help="Пересчитать только DebtByTerms (быстрее).",
        )
        parser.add_argument(
            "--snapshots-only",
            action="store_true",
            help="Пересчитать только AnalyticsSnapshot.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        debt_only: bool = options["debt_only"]
        snapshots_only: bool = options["snapshots_only"]

        if not snapshots_only:
            self._recalc_debt()
            self._recalc_planned_payments()

        if not debt_only:
            self._recalc_analytics_snapshot()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("✔ Пересчёт завершён."))

    # ──────────────────────────────────────────────

    def _recalc_debt(self) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("► Регистр задолженности по срокам"))
        from apps.registers.services import update_debt_statuses

        count = update_debt_statuses()
        self.stdout.write(self.style.SUCCESS(
            f"  ✔ Обновлено/создано записей: {count}"
        ))

    def _recalc_planned_payments(self) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("► Плановые платежи"))
        from apps.registers.services import update_planned_payments

        try:
            update_planned_payments()
            self.stdout.write(self.style.SUCCESS("  ✔ Статусы обновлены."))
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.WARNING(f"  ⚠ Пропущено: {exc}"))

    def _recalc_analytics_snapshot(self) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("► Аналитический снимок (10 KPI)"))
        try:
            from apps.analytics.services import recalculate_all_kpi

            snapshot = recalculate_all_kpi()
            self.stdout.write(self.style.SUCCESS(
                f"  ✔ Снимок на {snapshot.date}: "
                f"общий долг {snapshot.total_debt} ₽, "
                f"просрочка {snapshot.overdue_debt} ₽, "
                f"коэф. просрочки {snapshot.overdue_ratio}%"
            ))
        except ImportError:
            self.stdout.write(self.style.WARNING(
                "  ⚠ apps.analytics.services.recalculate_all_kpi не найдена, пропускаю."
            ))
        except Exception as exc:  # noqa: BLE001
            self.stdout.write(self.style.WARNING(f"  ⚠ Ошибка пересчёта: {exc}"))
