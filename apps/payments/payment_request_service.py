"""Сервис обработки заявок на оплату (PaymentRequest).

Содержит бизнес-логику переходов между статусами заявки и
интеграцию с 1С через OneCClient. Все операции пишут запись
в `PaymentRequestHistory` для аудита.

Используется views и management-командой push_payments_to_1c.
"""
from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import PaymentRequest, PaymentRequestHistory

logger = logging.getLogger("apps.payments")


# ──────────────────────────────────────────────
# Доменные исключения
# ──────────────────────────────────────────────


class WorkflowError(Exception):
    """Недопустимый переход или нарушение бизнес-правил."""


class OneCSyncError(Exception):
    """Ошибка при синхронизации заявки с 1С."""


# ──────────────────────────────────────────────
# Переходы статусов
# ──────────────────────────────────────────────


def _log_transition(
    pr: PaymentRequest, from_status: str, to_status: str,
    actor, comment: str = "",
) -> None:
    PaymentRequestHistory.objects.create(
        request=pr,
        from_status=from_status,
        to_status=to_status,
        actor=actor,
        comment=comment,
    )


@transaction.atomic
def submit_request(pr: PaymentRequest, actor) -> PaymentRequest:
    """Менеджер отправляет заявку на согласование."""
    if not pr.can_submit:
        raise WorkflowError(
            f"Заявку в статусе «{pr.get_status_display()}» нельзя отправить на согласование."
        )
    old_status = pr.status
    pr.status = PaymentRequest.Status.SUBMITTED
    pr.submitted_at = timezone.now()
    pr.rejection_reason = ""  # сброс при повторной подаче
    pr.save(update_fields=["status", "submitted_at", "rejection_reason", "updated_at"])
    _log_transition(pr, old_status, pr.status, actor, comment="Отправлено на согласование")
    return pr


@transaction.atomic
def approve_request(pr: PaymentRequest, actor) -> PaymentRequest:
    """Бухгалтер одобряет заявку."""
    if not pr.can_approve:
        raise WorkflowError(
            f"Заявку в статусе «{pr.get_status_display()}» нельзя одобрить."
        )
    old_status = pr.status
    pr.status = PaymentRequest.Status.APPROVED
    pr.reviewed_by = actor
    pr.reviewed_at = timezone.now()
    pr.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    _log_transition(pr, old_status, pr.status, actor, comment="Одобрено бухгалтером")
    return pr


@transaction.atomic
def reject_request(pr: PaymentRequest, actor, reason: str) -> PaymentRequest:
    """Бухгалтер отклоняет заявку с комментарием."""
    if not pr.can_reject:
        raise WorkflowError(
            f"Заявку в статусе «{pr.get_status_display()}» нельзя отклонить."
        )
    if not reason.strip():
        raise WorkflowError("Укажите причину отклонения.")

    old_status = pr.status
    pr.status = PaymentRequest.Status.REJECTED
    pr.reviewed_by = actor
    pr.reviewed_at = timezone.now()
    pr.rejection_reason = reason.strip()
    pr.save(update_fields=[
        "status", "reviewed_by", "reviewed_at",
        "rejection_reason", "updated_at",
    ])
    _log_transition(pr, old_status, pr.status, actor, comment=f"Отклонено: {reason}")
    return pr


@transaction.atomic
def cancel_request(pr: PaymentRequest, actor) -> PaymentRequest:
    """Отменить заявку (менеджер свою, или бухгалтер любую до отправки в 1С)."""
    if not pr.can_cancel:
        raise WorkflowError("Заявку нельзя отменить — она уже в 1С.")
    old_status = pr.status
    pr.status = PaymentRequest.Status.CANCELLED
    pr.save(update_fields=["status", "updated_at"])
    _log_transition(pr, old_status, pr.status, actor, comment="Отменено")
    return pr


# ──────────────────────────────────────────────
# Отправка в 1С
# ──────────────────────────────────────────────


def _build_1c_payload(pr: PaymentRequest, post: bool) -> dict[str, Any]:
    """Подготовить параметры для OneCClient.create_payment_order().

    Использует:
      * Ref_Key контрагента — из Counterparty.code_1c
      * Ref_Key договора    — из Contract.code_1c (если есть)
      * Организацию-плательщика — из настроек ONEC_INTEGRATION.DEFAULT_ORGANIZATION_KEY,
        либо первой организации в Catalog_Организации (можно потом улучшить)

    Если у заявки в `purpose` пустая строка, генерирует базовое назначение
    из реквизитов поступления-основания (если есть).
    """
    from django.conf import settings

    cfg = getattr(settings, "ONEC_INTEGRATION", {}) or {}

    if not pr.counterparty.code_1c:
        raise OneCSyncError(
            f"У контрагента «{pr.counterparty}» нет code_1c — "
            "сначала синхронизируйте справочник Контрагенты с 1С."
        )

    organization_key = cfg.get("DEFAULT_ORGANIZATION_KEY", "")
    if not organization_key:
        raise OneCSyncError(
            "Не задан settings.ONEC_INTEGRATION['DEFAULT_ORGANIZATION_KEY']. "
            "Укажите GUID вашей организации-плательщика в 1С."
        )

    purpose = pr.purpose.strip() or (
        f"Оплата по договору {pr.contract.number}" if pr.contract else
        f"Оплата поставщику {pr.counterparty.name}"
    )

    return {
        "organization_key": organization_key,
        "counterparty_key": pr.counterparty.code_1c,
        "contract_key": pr.contract.code_1c if (pr.contract and pr.contract.code_1c) else None,
        "amount": float(pr.amount),
        "date": pr.planned_date.strftime("%Y-%m-%dT12:00:00"),
        "purpose": purpose,
        "post": post,
    }


@transaction.atomic
def send_to_1c(pr: PaymentRequest, actor, *, post: bool = False) -> PaymentRequest:
    """Создать в 1С платёжное поручение по заявке.

    Параметр `post`:
        False — создать как черновик (Posted=False) — бухгалтер потом проверяет
        True  — создать сразу проведённым (Posted=True) — для срочных платежей

    Использует OneCClient. При сбое — записывает ошибку в pr.one_c_error
    и оставляет заявку в статусе APPROVED, чтобы можно было повторить попытку.
    """
    if not pr.can_send_to_1c:
        raise WorkflowError(
            f"Заявку в статусе «{pr.get_status_display()}» нельзя отправить в 1С. "
            "Сначала её должен согласовать бухгалтер."
        )

    # Импорт здесь, чтобы apps.payments не имел жёсткой зависимости от apps.api
    from apps.api.onec_client import OneCAuthError, OneCClient, OneCError

    try:
        params = _build_1c_payload(pr, post=post)
    except OneCSyncError as exc:
        pr.one_c_error = str(exc)
        pr.save(update_fields=["one_c_error", "updated_at"])
        raise

    try:
        client = OneCClient()
        # Прогрев соединения
        client.ping()
        result = client.create_payment_order(**params)
    except OneCAuthError as exc:
        pr.one_c_error = f"Ошибка авторизации в 1С: {exc}"
        pr.save(update_fields=["one_c_error", "updated_at"])
        logger.error("PaymentRequest #%s: auth error: %s", pr.id, exc)
        raise OneCSyncError(pr.one_c_error) from exc
    except OneCError as exc:
        pr.one_c_error = f"1С отклонила запрос: {exc}"
        pr.save(update_fields=["one_c_error", "updated_at"])
        logger.error("PaymentRequest #%s: OneCError: %s", pr.id, exc)
        raise OneCSyncError(pr.one_c_error) from exc
    except Exception as exc:  # noqa: BLE001
        pr.one_c_error = f"Непредвиденная ошибка: {exc}"
        pr.save(update_fields=["one_c_error", "updated_at"])
        logger.exception("PaymentRequest #%s: unexpected error", pr.id)
        raise OneCSyncError(pr.one_c_error) from exc

    # Успех — фиксируем результат
    old_status = pr.status
    pr.status = (
        PaymentRequest.Status.POSTED_IN_1C if post
        else PaymentRequest.Status.SENT_TO_1C
    )
    pr.one_c_doc_key = result.get("Ref_Key", "")
    pr.one_c_doc_number = result.get("Number", "")
    pr.sent_to_1c_at = timezone.now()
    pr.one_c_error = ""
    pr.save(update_fields=[
        "status", "one_c_doc_key", "one_c_doc_number",
        "sent_to_1c_at", "one_c_error", "updated_at",
    ])
    _log_transition(
        pr, old_status, pr.status, actor,
        comment=(
            f"Создан документ в 1С: №{pr.one_c_doc_number} "
            f"({'проведён' if post else 'черновик'})"
        ),
    )
    logger.info(
        "PaymentRequest #%s sent to 1C: ref=%s number=%s posted=%s",
        pr.id, pr.one_c_doc_key, pr.one_c_doc_number, post,
    )
    return pr
