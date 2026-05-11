"""Management-команда для batch-отправки одобренных заявок (PaymentRequest)
в 1С через REST OData.

Использует apps.payments.payment_request_service.send_to_1c для каждой
заявки в статусе APPROVED. По умолчанию создаёт черновики (Posted=False),
с флагом --post создаёт сразу проведённые документы.

Запуск:
    python manage.py push_payments_to_1c                  # все APPROVED как черновики
    python manage.py push_payments_to_1c --post           # все APPROVED проведёнными
    python manage.py push_payments_to_1c --request=N      # одну конкретную заявку
    python manage.py push_payments_to_1c --dry-run        # показать что будет отправлено
    python manage.py push_payments_to_1c --limit=5        # ограничить число
"""
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.payments.models import PaymentRequest
from apps.payments.payment_request_service import OneCSyncError, send_to_1c


class Command(BaseCommand):
    help = "Отправить одобренные заявки на оплату (PaymentRequest) в 1С."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--post",
            action="store_true",
            help="Создать документы сразу проведёнными (Posted=True). "
                 "По умолчанию — черновики, бухгалтер потом проводит.",
        )
        parser.add_argument(
            "--request",
            type=int,
            default=0,
            help="ID конкретной заявки для отправки (по умолчанию — все APPROVED).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать что было бы отправлено, но ничего не делать.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Максимальное число заявок за один запуск (0 = без ограничения).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        post: bool = options["post"]
        request_id: int = options["request"]
        dry_run: bool = options["dry_run"]
        limit: int = options["limit"]

        qs = PaymentRequest.objects.select_related(
            "counterparty", "contract", "related_receipt", "created_by",
        )

        if request_id:
            qs = qs.filter(id=request_id)
            if not qs.exists():
                raise CommandError(f"PaymentRequest #{request_id} не найден")
        else:
            qs = qs.filter(status=PaymentRequest.Status.APPROVED)

        if limit:
            qs = qs[:limit]

        requests = list(qs)
        if not requests:
            self.stdout.write(self.style.WARNING(
                "Нет одобренных заявок для отправки в 1С."
            ))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n► К отправке: {len(requests)} заявок "
            f"({'проведённых' if post else 'черновиков'})"
        ))

        ok = failed = 0
        for pr in requests:
            tag = self.style.SUCCESS("[готов]")
            if pr.status != PaymentRequest.Status.APPROVED:
                tag = self.style.ERROR(f"[пропуск:{pr.get_status_display()}]")
            self.stdout.write(
                f"  {tag} #{pr.id} | {pr.counterparty.name[:30]:30} | "
                f"{pr.amount:>12} ₽ | {pr.planned_date} | "
                f"{pr.purpose[:50]}"
            )

            if dry_run:
                continue
            if pr.status != PaymentRequest.Status.APPROVED:
                continue

            try:
                send_to_1c(pr, actor=pr.reviewed_by or pr.created_by, post=post)
                ok += 1
                self.stdout.write(self.style.SUCCESS(
                    f"      ↳ Создан в 1С: №{pr.one_c_doc_number} "
                    f"(Ref_Key: {pr.one_c_doc_key[:8]}...)"
                ))
            except OneCSyncError as exc:
                failed += 1
                self.stdout.write(self.style.ERROR(
                    f"      ↳ Ошибка: {exc}"
                ))

        self.stdout.write("")
        if dry_run:
            self.stdout.write(self.style.WARNING(
                "⚠ DRY-RUN: ни одна заявка не отправлена."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"═══ Отправлено: {ok}, ошибок: {failed} ═══"
            ))
