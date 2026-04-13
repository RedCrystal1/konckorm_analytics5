import logging

from apps.accounts.models import User

from .models import Notification

logger = logging.getLogger("apps.notifications")


def create_notification(user, type_, title, message, severity="info", link=""):
    """Создание уведомления для пользователя."""
    return Notification.objects.create(
        user=user,
        type=type_,
        severity=severity,
        title=title,
        message=message,
        link=link,
    )


def notify_overdue_payments():
    """Уведомления о просроченных платежах — отдельно по каждому контрагенту."""
    from apps.accounts.models import User
    from apps.registers.models import DebtByTerms

    overdue = DebtByTerms.objects.exclude(
        status=DebtByTerms.DebtStatus.CURRENT
    ).select_related("counterparty", "responsible_manager")

    if not overdue.exists():
        return 0

    # Группируем по контрагентам
    by_cp = {}
    for record in overdue:
        cp = record.counterparty
        by_cp.setdefault(cp.pk, {"cp": cp, "records": [], "total": Decimal("0")})
        by_cp[cp.pk]["records"].append(record)
        by_cp[cp.pk]["total"] += record.amount_rub

    created = 0
    recipients = User.objects.filter(
        role__in=["admin", "accountant", "manager"],
        notify_overdue=True,
        is_active=True,
    )

    for data in by_cp.values():
        cp = data["cp"]
        count = len(data["records"])
        total = data["total"]
        max_days = max(r.overdue_days for r in data["records"])
        severity = "critical" if max_days > 60 else "warning"

        for user in recipients:
            create_notification(
                user=user,
                type_=Notification.Type.OVERDUE,
                title=f"Просрочка: {cp.name} ({count} док.)",
                message=(
                    f"Контрагент: {cp.name} (ИНН: {cp.inn})\n"
                    f"Просроченных документов: {count}\n"
                    f"Общая сумма просрочки: {total:,.0f} руб.\n"
                    f"Максимальная просрочка: {max_days} дней"
                ),
                severity=severity,
                link=f"/registers/debt/?search={cp.name}&status=",
            )
            created += 1

    logger.info("Создано уведомлений о просрочке: %d", created)
    return created

def notify_cash_gaps(gaps):
    """Уведомления о кассовых разрывах."""
    users = User.objects.filter(
        role__in=["admin", "accountant", "manager"],
        notify_cash_gap=True,
        is_active=True,
    )

    created = 0
    for user in users:
        for gap in gaps:
            create_notification(
                user=user,
                type_=Notification.Type.CASH_GAP,
                title=f"Кассовый разрыв {gap['date']}",
                message=f"Прогнозируется дефицит {gap['deficit']:.2f} руб. на {gap['date']}.",
                severity=Notification.Severity.CRITICAL,
                link="/payments/alerts/",
            )
            created += 1

    return created


def notify_import_complete(session):
    """Уведомление о завершении импорта."""
    if not session.initiated_by:
        return

    status = session.get_status_display()
    type_ = Notification.Type.IMPORT_COMPLETE
    severity = Notification.Severity.INFO

    if session.status == "failed":
        type_ = Notification.Type.IMPORT_ERROR
        severity = Notification.Severity.CRITICAL

    create_notification(
        user=session.initiated_by,
        type_=type_,
        title=f"Импорт #{session.pk}: {status}",
        message=(
            f"Создано: {session.created_records}, "
            f"обновлено: {session.updated_records}, "
            f"ошибок: {session.error_records}, "
            f"дублей: {session.duplicates_found}."
        ),
        severity=severity,
        link=f"/import/{session.pk}/results/",
    )


def notify_upcoming_payments():
    """Уведомления о скором наступлении срока оплаты (за 3 дня)."""
    from datetime import timedelta

    from django.conf import settings
    from django.utils import timezone

    from apps.registers.models import PlannedPayment

    warning_days = getattr(settings, "UPCOMING_PAYMENT_WARNING_DAYS", 3)
    today = timezone.now().date()
    horizon = today + timedelta(days=warning_days)

    upcoming = PlannedPayment.objects.filter(
        status=PlannedPayment.PaymentStatus.PENDING,
        planned_date__gte=today,
        planned_date__lte=horizon,
    ).select_related("counterparty", "responsible_manager")

    if not upcoming.exists():
        return 0

    # Группируем по менеджерам
    managers = {}
    for pp in upcoming:
        mgr = pp.counterparty.responsible_manager if hasattr(pp.counterparty, "responsible_manager") else None
        if mgr and mgr.notify_overdue:
            managers.setdefault(mgr.pk, {"user": mgr, "payments": []})
            managers[mgr.pk]["payments"].append(pp)

    created = 0

    # Уведомления менеджерам
    for data in managers.values():
        total = sum(p.amount for p in data["payments"])
        count = len(data["payments"])
        create_notification(
            user=data["user"],
            type_=Notification.Type.OVERDUE,
            title=f"Скоро наступит срок оплаты: {count} платежей",
            message=f"В ближайшие {warning_days} дня(-ей) необходимо оплатить {count} платежей на сумму {total:,.0f} руб.",
            severity=Notification.Severity.WARNING,
            link=f"/payments/calendar/?year={timezone.now().year}&month={timezone.now().month}",
        )
        created += 1

    # Уведомления бухгалтерам/руководителям
    accountants = User.objects.filter(
        role__in=["admin", "accountant"],
        notify_overdue=True,
        is_active=True,
    )
    total_upcoming = sum(p.amount for p in upcoming)
    for user in accountants:
        create_notification(
            user=user,
            type_=Notification.Type.OVERDUE,
            title=f"Предстоящие платежи: {upcoming.count()} в ближайшие {warning_days} дня",
            message=f"Общая сумма предстоящих платежей: {total_upcoming:,.0f} руб. Проверьте платёжный календарь.",
            severity=Notification.Severity.INFO,
            link="/payments/calendar/",
        )
        created += 1

    logger.info("Создано уведомлений о предстоящих платежах: %d", created)
    return created
