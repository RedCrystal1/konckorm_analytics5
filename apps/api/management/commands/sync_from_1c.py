"""Management-команда для активной выгрузки данных из 1С в Django.

Поддерживаемые сущности (по порядку зависимостей):
    counterparties  — Справочник.Контрагенты → Counterparty
    contracts       — Справочник.ДоговорыКонтрагентов → Contract
    nomenclature    — Справочник.Номенклатура → Nomenclature
    receipts        — Документ.ПоступлениеТоваровУслуг → GoodsReceipt (+items)
    payments        — Документ.ПлатежноеПоручение и
                      Документ.СписаниеСРасчетногоСчета → PaymentOrder

Примеры::

    # Проверка связи
    python manage.py sync_from_1c --ping

    # Полная синхронизация в правильном порядке зависимостей
    python manage.py sync_from_1c --entities=counterparties,contracts,nomenclature,receipts,payments

    # Только документы (предполагает что справочники уже синхронизированы)
    python manage.py sync_from_1c --entities=receipts,payments

    # Сухой прогон
    python manage.py sync_from_1c --entities=receipts --dry-run

    # Без фильтра контрагентов (включить группы/гос.органы/физлиц)
    python manage.py sync_from_1c --entities=counterparties --include-all

    # Ограничить количество (полезно при отладке)
    python manage.py sync_from_1c --entities=receipts --limit=3
"""
from __future__ import annotations

import datetime as _dt
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.api.models import SyncSession
from apps.api.onec_client import OneCAuthError, OneCClient, OneCError
from apps.counterparties.models import Contract, Counterparty
from apps.directories.models import Nomenclature
from apps.documents.models import GoodsReceipt, GoodsReceiptItem, PaymentOrder


SUPPORTED_ENTITIES = {
    "counterparties",
    "contracts",
    "nomenclature",
    "receipts",
    "payments",
}

# Порядок применения сущностей: справочники → документы.
# Иначе документы не найдут своих контрагентов / номенклатуру.
APPLY_ORDER = ["counterparties", "contracts", "nomenclature", "receipts", "payments"]

ZERO_GUID = "00000000-0000-0000-0000-000000000000"


# ──────────────────────────────────────────────
# Утилиты парсинга
# ──────────────────────────────────────────────


def _parse_date(value: str | None) -> _dt.date | None:
    """1С отдаёт даты как ISO. Возвращает date или None для пустых/'нулевых' дат."""
    if not value:
        return None
    try:
        d = _dt.datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        return None
    if d.year < 1900:  # 1С отдаёт "0001-01-01T00:00:00" для пустых дат
        return None
    return d


def _to_decimal(value: Any) -> Decimal:
    """Привести числовое значение из OData к Decimal."""
    if value in (None, "", False):
        return Decimal("0")
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return Decimal("0")


def _is_zero_guid(value: str | None) -> bool:
    return not value or value == ZERO_GUID


# ──────────────────────────────────────────────
# Команда
# ──────────────────────────────────────────────


class Command(BaseCommand):
    help = "Активная синхронизация справочников и документов из 1С в Django через OData."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--entities",
            default="counterparties",
            help="Список сущностей через запятую. Поддерживается: "
            + ", ".join(sorted(SUPPORTED_ENTITIES)),
        )
        parser.add_argument(
            "--ping",
            action="store_true",
            help="Только проверить соединение и завершить.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Прочитать данные из 1С, но НЕ записывать в БД.",
        )
        parser.add_argument(
            "--include-all",
            action="store_true",
            help="Не фильтровать контрагентов (включить группы и гос. органы).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Максимальное число записей для импорта (0 = без ограничения).",
        )

    # ──────────────────────────────────────────────
    # Точка входа
    # ──────────────────────────────────────────────

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            client = OneCClient()
        except OneCError as exc:
            raise CommandError(str(exc))

        if options["ping"]:
            self._do_ping(client)
            return

        requested = [e.strip() for e in options["entities"].split(",") if e.strip()]
        unknown = set(requested) - SUPPORTED_ENTITIES
        if unknown:
            raise CommandError(
                f"Неизвестные сущности: {', '.join(unknown)}. "
                f"Допустимо: {', '.join(sorted(SUPPORTED_ENTITIES))}"
            )

        # Warm-up: первый минимальный запрос разбудит 1С:Фреш.
        # Это снимает таймаут на главной работе.
        self.stdout.write("Прогрев соединения с 1С...")
        try:
            client.ping()
        except OneCAuthError:
            raise CommandError("Авторизация в 1С отклонена (HTTP 401).")
        except OneCError as exc:
            raise CommandError(f"Не удалось разбудить 1С: {exc}")
        self.stdout.write(self.style.SUCCESS("✔ 1С отвечает, начинаем синхронизацию."))

        for entity in APPLY_ORDER:
            if entity not in requested:
                continue
            handler = getattr(self, f"_sync_{entity}")
            handler(
                client,
                dry_run=options["dry_run"],
                include_all=options["include_all"],
                limit=options["limit"],
            )

    # ──────────────────────────────────────────────
    # ping
    # ──────────────────────────────────────────────

    def _do_ping(self, client: OneCClient) -> None:
        self.stdout.write("Проверка связи с 1С...")
        try:
            client.ping()
        except OneCAuthError:
            raise CommandError("Авторизация в 1С отклонена (HTTP 401).")
        except OneCError as exc:
            raise CommandError(f"Ошибка связи: {exc}")
        self.stdout.write(self.style.SUCCESS(f"✔ Связь OK. URL: {client.base_url}"))

    # ──────────────────────────────────────────────
    # counterparties
    # ──────────────────────────────────────────────

    def _sync_counterparties(
        self, client: OneCClient, *, dry_run: bool, include_all: bool, limit: int
    ) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("\n► Контрагенты"))
        session = self._open_session("counterparties")

        received = created = updated = skipped = errors = 0
        try:
            for row in client.list_counterparties(exclude_folders=True):
                received += 1
                if limit and received > limit:
                    break

                if not include_all:
                    if row.get("ЮридическоеФизическоеЛицо") != "ЮридическоеЛицо":
                        skipped += 1
                        continue
                    if row.get("ГосударственныйОрган"):
                        skipped += 1
                        continue
                    if not (row.get("ИНН") or "").strip():
                        skipped += 1
                        continue

                try:
                    _, was_created = self._upsert_counterparty(row, dry_run=dry_run)
                    if was_created:
                        created += 1
                        self._line("new", row.get("Description", "")[:50],
                                   f"ИНН={row.get('ИНН') or '—'}")
                    else:
                        updated += 1
                        self._line("upd", row.get("Description", "")[:50],
                                   f"ИНН={row.get('ИНН') or '—'}")
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    self._err(row.get("Description", "?"), exc)

        except OneCError as exc:
            self._close_session(session, errors=1, error_msg=str(exc))
            raise CommandError(f"Сбой при выгрузке из 1С: {exc}")

        self._close_session(
            session, received=received, created=created,
            updated=updated, errors=errors,
            details={"skipped": skipped, "dry_run": dry_run, "include_all": include_all},
        )
        self._summary(received, created, updated, skipped, errors, dry_run)

    def _upsert_counterparty(self, row: dict, *, dry_run: bool):
        code_1c = row.get("Ref_Key") or ""
        defaults = {
            "name": (row.get("Description") or "").strip(),
            "full_name": (row.get("НаименованиеПолное") or row.get("Description") or "").strip(),
            "inn": (row.get("ИНН") or "").strip(),
            "kpp": (row.get("КПП") or "").strip(),
            "is_active": not row.get("DeletionMark", False),
        }
        if dry_run:
            return None, not Counterparty.objects.filter(code_1c=code_1c).exists()
        with transaction.atomic():
            return Counterparty.objects.update_or_create(code_1c=code_1c, defaults=defaults)

    # ──────────────────────────────────────────────
    # contracts
    # ──────────────────────────────────────────────

    def _sync_contracts(
        self, client: OneCClient, *, dry_run: bool, limit: int, **_: Any
    ) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("\n► Договоры"))
        session = self._open_session("contracts")

        received = created = updated = skipped = errors = 0
        cp_cache = self._counterparty_cache()

        try:
            for row in client.list_contracts():
                received += 1
                if limit and received > limit:
                    break

                owner_key = row.get("Owner_Key") or ""
                counterparty = cp_cache.get(owner_key)
                if counterparty is None:
                    skipped += 1
                    continue

                try:
                    was_created = self._upsert_contract(row, counterparty, dry_run=dry_run)
                    if was_created:
                        created += 1
                        self._line("new", row.get("Description", "")[:60],
                                   f"({counterparty.name[:30]})")
                    else:
                        updated += 1
                        self._line("upd", row.get("Description", "")[:60],
                                   f"({counterparty.name[:30]})")
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    self._err(row.get("Description", "?"), exc)
        except OneCError as exc:
            self._close_session(session, errors=1, error_msg=str(exc))
            raise CommandError(f"Сбой при выгрузке договоров: {exc}")

        self._close_session(
            session, received=received, created=created,
            updated=updated, errors=errors,
            details={"skipped_no_owner": skipped, "dry_run": dry_run},
        )
        self._summary(received, created, updated, skipped, errors, dry_run)

    def _upsert_contract(self, row: dict, counterparty: Counterparty, *, dry_run: bool) -> bool:
        code_1c = row.get("Ref_Key") or ""
        number = (row.get("НомерДоговораКонтрагента") or row.get("Description") or "")[:100]
        contract_date = (
            _parse_date(row.get("ДатаДоговораКонтрагента"))
            or _parse_date(row.get("Date"))
            or _dt.date.today()
        )
        defaults = {
            "counterparty": counterparty,
            "number": number,
            "date": contract_date,
            "is_active": not row.get("DeletionMark", False),
        }
        if dry_run:
            return not Contract.objects.filter(code_1c=code_1c).exists()
        with transaction.atomic():
            _, created = Contract.objects.update_or_create(
                code_1c=code_1c, defaults=defaults
            )
        return created

    # ──────────────────────────────────────────────
    # nomenclature
    # ──────────────────────────────────────────────

    def _sync_nomenclature(
        self, client: OneCClient, *, dry_run: bool, limit: int, **_: Any
    ) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("\n► Номенклатура"))
        session = self._open_session("nomenclature")

        received = created = updated = skipped = errors = 0
        seen_codes: set[str] = set()

        try:
            for row in client.list_nomenclature(exclude_folders=True):
                received += 1
                if limit and received > limit:
                    break

                ref_key = row.get("Ref_Key") or ""
                name = (row.get("Description") or "").strip()[:500]
                # AUTO-<guid8> чтобы можно было найти номенклатуру по Ref_Key.
                # В 1С коды могут быть пустыми/неуникальными.
                code = f"AUTO-{ref_key[:8]}"
                if code in seen_codes:
                    code = f"AUTO-{ref_key[:12]}"
                seen_codes.add(code)

                try:
                    was_created = self._upsert_nomenclature(name, code, dry_run=dry_run)
                    if was_created:
                        created += 1
                        self._line("new", name[:50], f"код={code}")
                    else:
                        updated += 1
                        self._line("upd", name[:50], f"код={code}")
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    self._err(name, exc)
        except OneCError as exc:
            self._close_session(session, errors=1, error_msg=str(exc))
            raise CommandError(f"Сбой при выгрузке номенклатуры: {exc}")

        self._close_session(
            session, received=received, created=created,
            updated=updated, errors=errors,
            details={"dry_run": dry_run},
        )
        self._summary(received, created, updated, skipped, errors, dry_run)

    def _upsert_nomenclature(self, name: str, code: str, *, dry_run: bool) -> bool:
        if dry_run:
            return not Nomenclature.objects.filter(code=code).exists()
        defaults = {"name": name, "is_active": True}
        with transaction.atomic():
            _, created = Nomenclature.objects.update_or_create(
                code=code, defaults=defaults
            )
        return created

    # ──────────────────────────────────────────────
    # receipts (Поступление товаров и услуг + Товары)
    # ──────────────────────────────────────────────

    def _sync_receipts(
        self, client: OneCClient, *, dry_run: bool, limit: int, **_: Any
    ) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("\n► Поступления товаров и услуг"))
        session = self._open_session("receipts")

        received = created = updated = skipped = errors = items_created = 0
        cp_cache = self._counterparty_cache()
        contr_cache = self._contract_cache()
        nom_cache: dict[str, Nomenclature] = {
            n.code: n for n in Nomenclature.objects.all()
        }

        try:
            for row in client.list_receipts(only_posted=True):
                received += 1
                if limit and received > limit:
                    break

                # См. комментарий в _sync_payments про варианты имён полей.
                # У поступлений обычно "Контрагент_Key", но подстрахуемся.
                cp_key = (
                    row.get("Контрагент_Key")
                    or row.get("Контрагент")
                    or ""
                )
                counterparty = cp_cache.get(cp_key) if cp_key else None
                if counterparty is None:
                    skipped += 1
                    continue

                contract = None
                ct_key = (
                    row.get("ДоговорКонтрагента_Key")
                    or row.get("ДоговорКонтрагента")
                    or ""
                )
                if not _is_zero_guid(ct_key):
                    contract = contr_cache.get(ct_key)

                doc_amount = _to_decimal(row.get("СуммаДокумента"))
                item_rows: list[dict] = []

                if not dry_run:
                    try:
                        item_rows = client.list_receipt_items(row["Ref_Key"])
                    except OneCError as exc:
                        self._err(f"строки документа {row.get('Number')}", exc)
                        item_rows = []
                    if doc_amount == 0 and item_rows:
                        doc_amount = sum(
                            _to_decimal(i.get("Сумма")) for i in item_rows
                        )

                try:
                    _, was_created, items_n = self._upsert_receipt(
                        row, counterparty, contract,
                        amount=doc_amount, items=item_rows,
                        nom_cache=nom_cache, dry_run=dry_run,
                    )
                    if was_created:
                        created += 1
                        marker = "new"
                    else:
                        updated += 1
                        marker = "upd"
                    items_created += items_n
                    self._line(
                        marker,
                        f"№{row.get('Number')} от {(row.get('Date') or '')[:10]}",
                        f"{counterparty.name[:25]} | {doc_amount} ₽ | строк: {items_n}",
                    )
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    self._err(f"{row.get('Number')} {row.get('Date')}", exc)
        except OneCError as exc:
            self._close_session(session, errors=1, error_msg=str(exc))
            raise CommandError(f"Сбой при выгрузке поступлений: {exc}")

        self._close_session(
            session, received=received, created=created,
            updated=updated, errors=errors,
            details={"skipped": skipped, "items_created": items_created, "dry_run": dry_run},
        )
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Получено: {received}, создано: {created}, обновлено: {updated}, "
            f"пропущено: {skipped}, ошибок: {errors}, "
            f"товарных строк: {items_created}."
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠ DRY-RUN: изменения НЕ записаны в БД."))

    def _upsert_receipt(
        self,
        row: dict,
        counterparty: Counterparty,
        contract: Contract | None,
        *,
        amount: Decimal,
        items: list[dict],
        nom_cache: dict[str, Nomenclature],
        dry_run: bool,
    ) -> tuple[GoodsReceipt | None, bool, int]:
        code_1c = row.get("Ref_Key") or ""
        doc_date = _parse_date(row.get("Date")) or _dt.date.today()

        # Срок оплаты: дата документа + дни из договора (или 30 по умолчанию)
        payment_days = contract.payment_days if contract else 30
        due_date = doc_date + _dt.timedelta(days=payment_days)

        defaults = {
            "number": (row.get("Number") or "")[:100],
            "date": doc_date,
            "counterparty": counterparty,
            "contract": contract,
            "amount": amount,
            "currency": "RUB",
            "payment_due_date": due_date,
            "is_paid": False,
            "paid_amount": Decimal("0"),
        }

        if dry_run:
            exists = GoodsReceipt.objects.filter(code_1c=code_1c).exists()
            return None, not exists, len(items)

        items_n = 0
        with transaction.atomic():
            obj, was_created = GoodsReceipt.objects.update_or_create(
                code_1c=code_1c, defaults=defaults,
            )
            obj.items.all().delete()  # перезапись строк
            for item in items:
                nom_key = item.get("Номенклатура_Key") or ""
                nomenclature = self._resolve_nomenclature(nom_key, nom_cache)
                if nomenclature is None:
                    continue
                GoodsReceiptItem.objects.create(
                    receipt=obj,
                    nomenclature=nomenclature,
                    quantity=_to_decimal(item.get("Количество")),
                    price=_to_decimal(item.get("Цена")),
                    amount=_to_decimal(item.get("Сумма")),
                    vat_rate=_to_decimal(item.get("СтавкаНДС") or 20),
                    vat_amount=_to_decimal(item.get("СуммаНДС")),
                )
                items_n += 1
        return obj, was_created, items_n

    def _resolve_nomenclature(
        self, nom_ref_key: str, nom_cache: dict[str, Nomenclature]
    ) -> Nomenclature | None:
        """Найти/создать номенклатуру по её GUID из 1С (через AUTO-<guid8> код)."""
        if _is_zero_guid(nom_ref_key):
            return None
        auto_code = f"AUTO-{nom_ref_key[:8]}"
        nom = nom_cache.get(auto_code)
        if nom:
            return nom
        nom, _ = Nomenclature.objects.get_or_create(
            code=auto_code,
            defaults={"name": f"Номенклатура {nom_ref_key[:8]}", "is_active": True},
        )
        nom_cache[auto_code] = nom
        return nom

    # ──────────────────────────────────────────────
    # payments
    # ──────────────────────────────────────────────

    def _sync_payments(
        self, client: OneCClient, *, dry_run: bool, limit: int, **_: Any
    ) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("\n► Платёжные документы"))
        session = self._open_session("payments")

        received = created = updated = skipped = errors = 0
        cp_cache = self._counterparty_cache()
        contr_cache = self._contract_cache()

        # Берём «Списание с р/с» как источник истины — это фактические платежи.
        # «Платёжное поручение» — намерение, может быть не проведено в банке.
        sources = [
            ("Списание с р/с", client.list_write_offs),
            ("Платёжное поручение", client.list_payment_orders),
        ]

        try:
            for source_name, fetcher in sources:
                count_for_source = 0
                for row in fetcher(only_posted=True):
                    received += 1
                    count_for_source += 1
                    if limit and count_for_source > limit:
                        break

                    # В разных типах документов 1С ссылка на контрагента может
                    # быть либо с суффиксом _Key (обычная ссылка),
                    # либо без него (полиморфная ссылка с отдельным полем _Type).
                    # Списание с р/с использует полиморфную форму "Контрагент",
                    # а платёжное поручение — обычную "Контрагент_Key".
                    cp_key = (
                        row.get("Контрагент_Key")
                        or row.get("Контрагент")
                        or ""
                    )
                    counterparty = cp_cache.get(cp_key) if cp_key else None

                    if counterparty is None:
                        # Платёж в адрес неимпортированного контрагента
                        # (бюджет, сотрудник, банк) — пропускаем
                        skipped += 1
                        continue

                    contract = None
                    ct_key = (
                        row.get("ДоговорКонтрагента_Key")
                        or row.get("ДоговорКонтрагента")
                        or ""
                    )
                    if not _is_zero_guid(ct_key):
                        contract = contr_cache.get(ct_key)

                    try:
                        was_created = self._upsert_payment(
                            row, counterparty, contract, dry_run=dry_run,
                        )
                        if was_created:
                            created += 1
                            marker = "new"
                        else:
                            updated += 1
                            marker = "upd"
                        amount = _to_decimal(row.get("СуммаДокумента"))
                        self._line(
                            marker,
                            f"№{row.get('Number')} от {(row.get('Date') or '')[:10]}",
                            f"{counterparty.name[:25]} | {amount} ₽ | {source_name}",
                        )
                    except Exception as exc:  # noqa: BLE001
                        errors += 1
                        self._err(f"{row.get('Number')} {row.get('Date')}", exc)
        except OneCError as exc:
            self._close_session(session, errors=1, error_msg=str(exc))
            raise CommandError(f"Сбой при выгрузке платежей: {exc}")

        self._close_session(
            session, received=received, created=created,
            updated=updated, errors=errors,
            details={"skipped": skipped, "dry_run": dry_run},
        )
        self._summary(received, created, updated, skipped, errors, dry_run)

    def _upsert_payment(
        self,
        row: dict,
        counterparty: Counterparty,
        contract: Contract | None,
        *,
        dry_run: bool,
    ) -> bool:
        code_1c = row.get("Ref_Key") or ""
        doc_date = _parse_date(row.get("Date")) or _dt.date.today()
        defaults = {
            "number": (row.get("Number") or "")[:100],
            "date": doc_date,
            "counterparty": counterparty,
            "contract": contract,
            "amount": _to_decimal(row.get("СуммаДокумента")),
            "currency": "RUB",
            "payment_purpose": (row.get("НазначениеПлатежа") or "")[:5000],
        }
        if dry_run:
            return not PaymentOrder.objects.filter(code_1c=code_1c).exists()
        with transaction.atomic():
            _, created = PaymentOrder.objects.update_or_create(
                code_1c=code_1c, defaults=defaults,
            )
        return created

    # ──────────────────────────────────────────────
    # Кэши
    # ──────────────────────────────────────────────

    def _counterparty_cache(self) -> dict[str, Counterparty]:
        return {c.code_1c: c for c in Counterparty.objects.exclude(code_1c__isnull=True)}

    def _contract_cache(self) -> dict[str, Contract]:
        return {c.code_1c: c for c in Contract.objects.exclude(code_1c__isnull=True)}

    # ──────────────────────────────────────────────
    # SyncSession
    # ──────────────────────────────────────────────

    def _open_session(self, entity: str) -> SyncSession:
        return SyncSession.objects.create(
            direction=SyncSession.Direction.INCOMING,
            endpoint=f"manage.py sync_from_1c {entity}",
        )

    def _close_session(
        self,
        session: SyncSession,
        *,
        received: int = 0,
        created: int = 0,
        updated: int = 0,
        errors: int = 0,
        error_msg: str = "",
        details: dict | None = None,
    ) -> None:
        session.records_received = received
        session.records_created = created
        session.records_updated = updated
        session.records_errors = errors
        session.error_message = error_msg
        session.status = (
            SyncSession.Status.FAILED if (errors or error_msg)
            else SyncSession.Status.COMPLETED
        )
        session.completed_at = timezone.now()
        if details:
            session.details = details
        session.save()

    # ──────────────────────────────────────────────
    # stdout
    # ──────────────────────────────────────────────

    def _line(self, marker: str, title: str, extra: str = "") -> None:
        if marker == "new":
            tag = self.style.SUCCESS("[new]")
        elif marker == "upd":
            tag = self.style.WARNING("[upd]")
        else:
            tag = self.style.NOTICE(f"[{marker}]")
        self.stdout.write(f"  {tag} {title}  {extra}")

    def _err(self, title: str, exc: Exception) -> None:
        self.stdout.write(self.style.ERROR(f"  [err] {title}: {exc}"))

    def _summary(
        self,
        received: int, created: int, updated: int, skipped: int, errors: int,
        dry_run: bool,
    ) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Получено: {received}, создано: {created}, обновлено: {updated}, "
            f"пропущено: {skipped}, ошибок: {errors}."
        ))
        if dry_run:
            self.stdout.write(self.style.WARNING("⚠ DRY-RUN: изменения НЕ записаны в БД."))
