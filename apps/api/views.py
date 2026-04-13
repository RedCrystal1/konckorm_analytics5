import json
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import SyncSession

logger = logging.getLogger("apps.api")


def _parse_json(request):
    """Парсинг JSON из тела запроса."""
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError) as e:
        return None


def _parse_date(date_str):
    """Парсинг даты из строки."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def _start_session(request, endpoint, direction="incoming"):
    """Создание сессии синхронизации."""
    return SyncSession.objects.create(
        direction=direction,
        endpoint=endpoint,
        api_token=getattr(request, "api_token", None),
    )


def _complete_session(session, created=0, updated=0, errors=0, error_msg=""):
    """Завершение сессии синхронизации. Уведомляет администраторов при сбоях."""
    session.records_created = created
    session.records_updated = updated
    session.records_errors = errors
    session.error_message = error_msg
    session.status = SyncSession.Status.FAILED if error_msg else SyncSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.save()

    # Уведомление администраторам при сбоях
    if errors > 0 or error_msg:
        try:
            from apps.accounts.models import User
            from apps.notifications.models import Notification

            admins = User.objects.filter(
                role__in=["admin", "accountant"], is_active=True
            )
            for admin_user in admins:
                Notification.objects.create(
                    user=admin_user,
                    type=Notification.Type.IMPORT_ERROR if error_msg else Notification.Type.SYSTEM,
                    severity="critical" if error_msg else "warning",
                    title=f"Сбой синхронизации с 1С: {session.endpoint}",
                    message=(
                        f"Направление: {session.get_direction_display()}\n"
                        f"Эндпоинт: {session.endpoint}\n"
                        f"Создано: {created}, обновлено: {updated}, ошибок: {errors}\n"
                        f"{'Ошибка: ' + error_msg if error_msg else ''}"
                    ),
                    link="/admin/api/syncsession/",
                )
            logger.warning(
                "Сбой синхронизации %s: ошибок=%d, сообщение=%s",
                session.endpoint, errors, error_msg
            )
        except Exception as e:
            logger.error("Не удалось отправить уведомление о сбое: %s", e)


# ══════════════════════════════════════════════
# ДОКУМЕНТАЦИЯ API
# ══════════════════════════════════════════════


def api_docs(request):
    """Документация API."""
    docs = {
        "version": "1.0",
        "description": "API для интеграции с 1С: Бухгалтерия",
        "auth": "Заголовок Authorization: Token <key>",
        "endpoints": {
            "POST /api/v1/sync/counterparties/": {
                "description": "Синхронизация справочника контрагентов",
                "body": {
                    "counterparties": [
                        {
                            "code": "КА-001",
                            "name": "ООО Пример",
                            "full_name": "Общество с ограниченной ответственностью Пример",
                            "inn": "7701234567",
                            "kpp": "770101001",
                            "legal_address": "г. Москва, ул. Примерная, 1",
                            "actual_address": "г. Москва, ул. Примерная, 1",
                            "phone": "+7(495)111-22-33",
                            "email": "info@example.ru",
                            "contact_person": "Иванов И.И.",
                            "is_key_supplier": False,
                        }
                    ]
                },
            },
            "POST /api/v1/sync/contracts/": {
                "description": "Синхронизация справочника договоров",
                "body": {
                    "contracts": [
                        {
                            "code": "Д-001",
                            "counterparty_code": "КА-001",
                            "number": "12/2025",
                            "date": "2025-01-15",
                            "kind": "supply",
                            "currency": "RUB",
                            "payment_term_type": "deferred",
                            "payment_days": 30,
                            "credit_limit": 1000000,
                        }
                    ]
                },
            },
            "POST /api/v1/sync/documents/receipts/": {
                "description": "Синхронизация документов поступления товаров и услуг",
                "body": {
                    "documents": [
                        {
                            "code": "ПТУ-001",
                            "number": "00000123",
                            "date": "2025-03-15",
                            "counterparty_code": "КА-001",
                            "contract_code": "Д-001",
                            "amount": 150000.50,
                            "payment_due_date": "2025-04-14",
                            "items": [
                                {
                                    "nomenclature_code": "NOM-001",
                                    "quantity": 1000,
                                    "price": 150.05,
                                    "amount": 150050.00,
                                    "vat_rate": 20,
                                }
                            ],
                        }
                    ]
                },
            },
            "POST /api/v1/sync/documents/payments/": {
                "description": "Синхронизация платёжных поручений",
                "body": {
                    "documents": [
                        {
                            "code": "ПП-001",
                            "number": "00000456",
                            "date": "2025-03-20",
                            "counterparty_code": "КА-001",
                            "contract_code": "Д-001",
                            "amount": 150000.50,
                            "payment_purpose": "Оплата по договору 12/2025",
                            "related_receipt_code": "ПТУ-001",
                        }
                    ]
                },
            },
            "POST /api/v1/sync/balances/": {
                "description": "Синхронизация остатков по счетам (60.01, 60.02, 60.21, 76)",
                "body": {
                    "balances": [
                        {
                            "account": "60.01",
                            "counterparty_code": "КА-001",
                            "contract_code": "Д-001",
                            "balance_date": "2025-04-01",
                            "debit": 50000,
                            "credit": 200000,
                            "balance": -150000,
                        }
                    ]
                },
            },
            "GET /api/v1/export/reconciliations/": {
                "description": "Выгрузка результатов сверок для загрузки в 1С",
                "params": {"since": "2025-01-01 (опционально)"},
            },
            "GET /api/v1/export/debt-status/": {
                "description": "Выгрузка статусов задолженности (сомнительная и т.д.)",
            },
            "GET /api/v1/export/payment-recommendations/": {
                "description": "Рекомендуемые даты и приоритеты оплат",
            },
            "GET /api/v1/status/": {
                "description": "Статус системы и последняя синхронизация",
            },
        },
    }
    return JsonResponse(docs, json_dumps_params={"ensure_ascii": False, "indent": 2})


# ══════════════════════════════════════════════
# ВХОДЯЩИЙ ПОТОК: 1С → Платформа
# ══════════════════════════════════════════════


@csrf_exempt
@require_http_methods(["POST"])
def sync_counterparties(request):
    """Синхронизация справочника контрагентов из 1С."""
    from apps.counterparties.models import Counterparty

    data = _parse_json(request)
    if not data or "counterparties" not in data:
        return JsonResponse({"error": "Ожидается JSON с ключом 'counterparties'"}, status=400)

    session = _start_session(request, "/api/v1/sync/counterparties/")
    items = data["counterparties"]
    session.records_received = len(items)
    created = updated = errors = 0

    for item in items:
        try:
            code = item.get("code", "").strip()
            if not code:
                errors += 1
                continue

            obj, is_new = Counterparty.objects.update_or_create(
                code_1c=code,
                defaults={
                    "name": item.get("name", ""),
                    "full_name": item.get("full_name", ""),
                    "inn": item.get("inn", ""),
                    "kpp": item.get("kpp", ""),
                    "legal_address": item.get("legal_address", ""),
                    "actual_address": item.get("actual_address", ""),
                    "phone": item.get("phone", ""),
                    "email": item.get("email", ""),
                    "contact_person": item.get("contact_person", ""),
                    "is_key_supplier": item.get("is_key_supplier", False),
                },
            )
            if is_new:
                created += 1
            else:
                updated += 1

        except Exception as e:
            errors += 1
            logger.error("Ошибка синхронизации контрагента %s: %s", item.get("code"), e)

    _complete_session(session, created, updated, errors)
    session.save()

    return JsonResponse({
        "status": "ok",
        "received": len(items),
        "created": created,
        "updated": updated,
        "errors": errors,
        "session_id": session.pk,
    })


@csrf_exempt
@require_http_methods(["POST"])
def sync_contracts(request):
    """Синхронизация справочника договоров из 1С."""
    from apps.counterparties.models import Contract, Counterparty

    data = _parse_json(request)
    if not data or "contracts" not in data:
        return JsonResponse({"error": "Ожидается JSON с ключом 'contracts'"}, status=400)

    session = _start_session(request, "/api/v1/sync/contracts/")
    items = data["contracts"]
    session.records_received = len(items)
    created = updated = errors = 0

    for item in items:
        try:
            code = item.get("code", "").strip()
            cp_code = item.get("counterparty_code", "").strip()
            if not code or not cp_code:
                errors += 1
                continue

            try:
                counterparty = Counterparty.objects.get(code_1c=cp_code)
            except Counterparty.DoesNotExist:
                errors += 1
                logger.warning("Контрагент с кодом %s не найден", cp_code)
                continue

            contract_date = _parse_date(item.get("date"))
            valid_from = _parse_date(item.get("valid_from"))
            valid_to = _parse_date(item.get("valid_to"))

            obj, is_new = Contract.objects.update_or_create(
                code_1c=code,
                defaults={
                    "counterparty": counterparty,
                    "number": item.get("number", ""),
                    "name": item.get("name", ""),
                    "date": contract_date or timezone.now().date(),
                    "kind": item.get("kind", "supply"),
                    "currency": item.get("currency", "RUB"),
                    "payment_term_type": item.get("payment_term_type", "deferred"),
                    "payment_days": int(item.get("payment_days", 30)),
                    "credit_limit": _to_decimal(item.get("credit_limit")),
                    "penalty_rate": _to_decimal(item.get("penalty_rate")),
                    "valid_from": valid_from,
                    "valid_to": valid_to,
                    "is_active": item.get("is_active", True),
                },
            )
            if is_new:
                created += 1
            else:
                updated += 1

        except Exception as e:
            errors += 1
            logger.error("Ошибка синхронизации договора %s: %s", item.get("code"), e)

    _complete_session(session, created, updated, errors)

    return JsonResponse({
        "status": "ok", "received": len(items),
        "created": created, "updated": updated, "errors": errors,
    })


@csrf_exempt
@require_http_methods(["POST"])
def sync_receipts(request):
    """Синхронизация документов поступления товаров и услуг."""
    from apps.counterparties.models import Contract, Counterparty
    from apps.directories.models import Nomenclature
    from apps.documents.models import GoodsReceipt, GoodsReceiptItem

    data = _parse_json(request)
    if not data or "documents" not in data:
        return JsonResponse({"error": "Ожидается JSON с ключом 'documents'"}, status=400)

    session = _start_session(request, "/api/v1/sync/documents/receipts/")
    items = data["documents"]
    session.records_received = len(items)
    created = updated = errors = 0

    for item in items:
        try:
            code = item.get("code", "").strip()
            cp_code = item.get("counterparty_code", "").strip()
            if not code or not cp_code:
                errors += 1
                continue

            try:
                counterparty = Counterparty.objects.get(code_1c=cp_code)
            except Counterparty.DoesNotExist:
                errors += 1
                continue

            contract = None
            contract_code = item.get("contract_code", "").strip()
            if contract_code:
                contract = Contract.objects.filter(code_1c=contract_code).first()

            doc_date = _parse_date(item.get("date"))
            due_date = _parse_date(item.get("payment_due_date"))
            amount = _to_decimal(item.get("amount", 0))

            receipt, is_new = GoodsReceipt.objects.update_or_create(
                code_1c=code,
                defaults={
                    "number": item.get("number", ""),
                    "date": doc_date or timezone.now().date(),
                    "counterparty": counterparty,
                    "contract": contract,
                    "amount": amount,
                    "currency": item.get("currency", "RUB"),
                    "payment_due_date": due_date or doc_date,
                    "notes": item.get("notes", ""),
                },
            )

            # Товарные строки
            if "items" in item and item["items"]:
                if not is_new:
                    receipt.items.all().delete()
                for line in item["items"]:
                    nom_code = line.get("nomenclature_code", "")
                    nomenclature = Nomenclature.objects.filter(code=nom_code).first()
                    if not nomenclature:
                        continue
                    GoodsReceiptItem.objects.create(
                        receipt=receipt,
                        nomenclature=nomenclature,
                        quantity=_to_decimal(line.get("quantity", 0)),
                        price=_to_decimal(line.get("price", 0)),
                        amount=_to_decimal(line.get("amount", 0)),
                        vat_rate=_to_decimal(line.get("vat_rate", 20)),
                        vat_amount=_to_decimal(line.get("vat_amount", 0)),
                    )

            if is_new:
                created += 1
            else:
                updated += 1

        except Exception as e:
            errors += 1
            logger.error("Ошибка синхронизации поступления %s: %s", item.get("code"), e)

    _complete_session(session, created, updated, errors)

    return JsonResponse({
        "status": "ok", "received": len(items),
        "created": created, "updated": updated, "errors": errors,
    })


@csrf_exempt
@require_http_methods(["POST"])
def sync_payments(request):
    """Синхронизация платёжных поручений."""
    from apps.counterparties.models import Contract, Counterparty
    from apps.documents.models import GoodsReceipt, PaymentOrder

    data = _parse_json(request)
    if not data or "documents" not in data:
        return JsonResponse({"error": "Ожидается JSON с ключом 'documents'"}, status=400)

    session = _start_session(request, "/api/v1/sync/documents/payments/")
    items = data["documents"]
    session.records_received = len(items)
    created = updated = errors = 0

    for item in items:
        try:
            code = item.get("code", "").strip()
            cp_code = item.get("counterparty_code", "").strip()
            if not code or not cp_code:
                errors += 1
                continue

            try:
                counterparty = Counterparty.objects.get(code_1c=cp_code)
            except Counterparty.DoesNotExist:
                errors += 1
                continue

            contract = None
            if item.get("contract_code"):
                contract = Contract.objects.filter(code_1c=item["contract_code"]).first()

            related_receipt = None
            if item.get("related_receipt_code"):
                related_receipt = GoodsReceipt.objects.filter(code_1c=item["related_receipt_code"]).first()

            doc_date = _parse_date(item.get("date"))
            amount = _to_decimal(item.get("amount", 0))

            obj, is_new = PaymentOrder.objects.update_or_create(
                code_1c=code,
                defaults={
                    "number": item.get("number", ""),
                    "date": doc_date or timezone.now().date(),
                    "counterparty": counterparty,
                    "contract": contract,
                    "amount": amount,
                    "payment_purpose": item.get("payment_purpose", ""),
                    "related_receipt": related_receipt,
                },
            )

            # Обновляем оплату в поступлении
            if related_receipt and is_new:
                related_receipt.paid_amount += amount
                if related_receipt.paid_amount >= related_receipt.amount:
                    related_receipt.is_paid = True
                related_receipt.save(update_fields=["paid_amount", "is_paid"])

            if is_new:
                created += 1
            else:
                updated += 1

        except Exception as e:
            errors += 1
            logger.error("Ошибка синхронизации платёжки %s: %s", item.get("code"), e)

    _complete_session(session, created, updated, errors)

    return JsonResponse({
        "status": "ok", "received": len(items),
        "created": created, "updated": updated, "errors": errors,
    })


@csrf_exempt
@require_http_methods(["POST"])
def sync_balances(request):
    """Синхронизация остатков по счетам бухучёта."""
    from apps.counterparties.models import Contract, Counterparty
    from apps.documents.models import AccountBalance

    data = _parse_json(request)
    if not data or "balances" not in data:
        return JsonResponse({"error": "Ожидается JSON с ключом 'balances'"}, status=400)

    session = _start_session(request, "/api/v1/sync/balances/")
    items = data["balances"]
    session.records_received = len(items)
    created = updated = errors = 0

    valid_accounts = ["60.01", "60.02", "60.21", "62", "76"]

    for item in items:
        try:
            account = item.get("account", "").strip()
            cp_code = item.get("counterparty_code", "").strip()
            bal_date = _parse_date(item.get("balance_date"))

            if account not in valid_accounts or not cp_code or not bal_date:
                errors += 1
                continue

            try:
                counterparty = Counterparty.objects.get(code_1c=cp_code)
            except Counterparty.DoesNotExist:
                errors += 1
                continue

            contract = None
            if item.get("contract_code"):
                contract = Contract.objects.filter(code_1c=item["contract_code"]).first()

            obj, is_new = AccountBalance.objects.update_or_create(
                account=account,
                counterparty=counterparty,
                balance_date=bal_date,
                defaults={
                    "contract": contract,
                    "debit": _to_decimal(item.get("debit", 0)),
                    "credit": _to_decimal(item.get("credit", 0)),
                    "balance": _to_decimal(item.get("balance", 0)),
                },
            )
            if is_new:
                created += 1
            else:
                updated += 1

        except Exception as e:
            errors += 1
            logger.error("Ошибка синхронизации остатка: %s", e)

    _complete_session(session, created, updated, errors)

    return JsonResponse({
        "status": "ok", "received": len(items),
        "created": created, "updated": updated, "errors": errors,
    })


# ══════════════════════════════════════════════
# ИСХОДЯЩИЙ ПОТОК: Платформа → 1С
# ══════════════════════════════════════════════


@require_http_methods(["GET"])
def export_reconciliations(request):
    """Выгрузка результатов сверок для 1С."""
    from apps.reconciliation.models import ReconciliationAct

    since = _parse_date(request.GET.get("since"))
    qs = ReconciliationAct.objects.select_related("counterparty").all()
    if since:
        qs = qs.filter(created_at__date__gte=since)

    session = _start_session(request, "/api/v1/export/reconciliations/", "outgoing")

    results = []
    for act in qs:
        discrepancies = []
        for d in act.discrepancies.all():
            discrepancies.append({
                "document_ref": d.document_ref,
                "our_amount": str(d.our_amount),
                "their_amount": str(d.their_amount) if d.their_amount else None,
                "discrepancy_amount": str(d.discrepancy_amount),
                "reason": d.reason,
                "status": d.status,
            })

        results.append({
            "counterparty_code": act.counterparty.code_1c,
            "counterparty_inn": act.counterparty.inn,
            "period_start": str(act.period_start),
            "period_end": str(act.period_end),
            "our_balance": str(act.our_balance),
            "their_balance": str(act.their_balance) if act.their_balance else None,
            "is_matched": act.is_matched,
            "created_at": act.created_at.isoformat(),
            "discrepancies": discrepancies,
        })

    _complete_session(session, created=len(results))

    return JsonResponse({
        "status": "ok",
        "count": len(results),
        "reconciliations": results,
    }, json_dumps_params={"ensure_ascii": False})


@require_http_methods(["GET"])
def export_debt_status(request):
    """Выгрузка статусов задолженности для 1С (сомнительная, просроченная)."""
    from apps.registers.models import DebtByTerms

    session = _start_session(request, "/api/v1/export/debt-status/", "outgoing")

    records = DebtByTerms.objects.select_related(
        "counterparty", "source_document"
    ).exclude(status=DebtByTerms.DebtStatus.CURRENT)

    results = []
    for r in records:
        results.append({
            "counterparty_code": r.counterparty.code_1c,
            "counterparty_inn": r.counterparty.inn,
            "document_code": r.source_document.code_1c,
            "document_number": r.source_document.number,
            "amount_rub": str(r.amount_rub),
            "overdue_days": r.overdue_days,
            "status": r.status,
            "status_display": r.get_status_display(),
            "planned_payment_date": str(r.planned_payment_date),
        })

    _complete_session(session, created=len(results))

    return JsonResponse({
        "status": "ok",
        "count": len(results),
        "debt_records": results,
    }, json_dumps_params={"ensure_ascii": False})


@require_http_methods(["GET"])
def export_payment_recommendations(request):
    """Рекомендуемые даты и приоритеты оплат для 1С."""
    from apps.registers.models import PlannedPayment

    session = _start_session(request, "/api/v1/export/payment-recommendations/", "outgoing")

    payments = PlannedPayment.objects.select_related(
        "counterparty", "source_document"
    ).filter(status__in=["pending", "overdue"]).order_by("planned_date")

    results = []
    for p in payments:
        results.append({
            "counterparty_code": p.counterparty.code_1c,
            "counterparty_inn": p.counterparty.inn,
            "counterparty_name": p.counterparty.name,
            "document_number": p.source_document.number,
            "planned_date": str(p.planned_date),
            "amount": str(p.amount),
            "priority": p.priority,
            "priority_display": p.get_priority_display(),
            "status": p.status,
            "is_overdue": p.status == "overdue",
        })

    _complete_session(session, created=len(results))

    return JsonResponse({
        "status": "ok",
        "count": len(results),
        "recommendations": results,
    }, json_dumps_params={"ensure_ascii": False})


@require_http_methods(["GET"])
def api_status(request):
    """Статус системы и последняя синхронизация."""
    from apps.analytics.models import AnalyticsSnapshot

    last_sync = SyncSession.objects.order_by("-started_at").first()
    last_kpi = None
    try:
        last_kpi = AnalyticsSnapshot.objects.latest()
    except AnalyticsSnapshot.DoesNotExist:
        pass

    return JsonResponse({
        "status": "ok",
        "system": "КонцКорма.Аналитика",
        "version": "1.0",
        "server_time": timezone.now().isoformat(),
        "last_sync": {
            "direction": last_sync.get_direction_display() if last_sync else None,
            "status": last_sync.get_status_display() if last_sync else None,
            "time": last_sync.started_at.isoformat() if last_sync else None,
            "records": last_sync.records_received if last_sync else 0,
        } if last_sync else None,
        "last_kpi": {
            "date": str(last_kpi.date) if last_kpi else None,
            "total_debt": str(last_kpi.total_debt) if last_kpi else None,
            "overdue_ratio": str(last_kpi.overdue_ratio) if last_kpi else None,
        } if last_kpi else None,
    })


# ══════════════════════════════════════════════
# УТИЛИТЫ
# ══════════════════════════════════════════════


def _to_decimal(value):
    """Безопасная конвертация в Decimal."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
