from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Notification


@login_required
def notification_list_view(request):
    """Список уведомлений с фильтрацией."""
    qs = request.user.notifications.all()

    # Фильтр по типу
    type_filter = request.GET.get("type")
    if type_filter:
        qs = qs.filter(type=type_filter)

    # Фильтр по статусу
    status_filter = request.GET.get("status")
    if status_filter == "unread":
        qs = qs.filter(is_read=False)
    elif status_filter == "read":
        qs = qs.filter(is_read=True)

    # Счётчики для вкладок
    all_count = request.user.notifications.count()
    unread_count = request.user.notifications.filter(is_read=False).count()

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "notifications/notification_center.html",
        {
            "page_obj": page,
            "notifications_list": page,
            "type_filter": type_filter,
            "status_filter": status_filter,
            "all_count": all_count,
            "unread_count_total": unread_count,
        },
    )


@login_required
def notification_detail_view(request, pk):
    """Детальный просмотр уведомления."""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)

    # Автоматически отмечаем как прочитанное при открытии
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])

    return render(
        request,
        "notifications/notification_detail.html",
        {"notification": notification},
    )


@login_required
def notification_settings_view(request):
    """Настройки уведомлений (перенаправление на профиль)."""
    return redirect("accounts:profile_edit")


@login_required
def mark_as_read(request, pk):
    """Отметить уведомление как прочитанное и перейти по ссылке."""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.read_at = timezone.now()
    notification.save(update_fields=["is_read", "read_at"])

    if notification.link:
        return redirect(notification.link)
    return redirect("notifications:detail", pk=pk)


@login_required
def mark_all_read(request):
    """Отметить все уведомления как прочитанные."""
    if request.method == "POST":
        updated = request.user.notifications.filter(is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        messages.success(request, f"Отмечено как прочитанные: {updated} уведомлений.")
    return redirect("notifications:list")


@login_required
def notification_delete(request, pk):
    """Удаление уведомления."""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    if request.method == "POST":
        notification.delete()
        messages.success(request, "Уведомление удалено.")
    return redirect("notifications:list")


@login_required
def delete_all_read(request):
    """Удалить все прочитанные уведомления."""
    if request.method == "POST":
        deleted, _ = request.user.notifications.filter(is_read=True).delete()
        messages.success(request, f"Удалено прочитанных: {deleted}.")
    return redirect("notifications:list")


# ── HTMX ──


@login_required
def htmx_notification_dropdown(request):
    """HTMX: выпадающий список последних уведомлений."""
    notifications = request.user.notifications.filter(is_read=False)[:10]
    return render(
        request,
        "notifications/partials/_notification_dropdown.html",
        {"notifications_list": notifications},
    )


@login_required
def htmx_notification_count(request):
    """HTMX: бейдж с количеством непрочитанных."""
    count = request.user.notifications.filter(is_read=False).count()
    if count > 0:
        return HttpResponse(f'<span class="badge bg-danger">{count}</span>')
    return HttpResponse("")
