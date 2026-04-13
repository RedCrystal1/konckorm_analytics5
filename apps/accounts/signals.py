from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import ActivityLog


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    ip = _get_client_ip(request)
    ActivityLog.objects.create(
        user=user,
        action="login",
        object_type="accounts.User",
        object_id=str(user.pk),
        object_repr=str(user),
        ip_address=ip,
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    if user:
        ip = _get_client_ip(request)
        ActivityLog.objects.create(
            user=user,
            action="logout",
            object_type="accounts.User",
            object_id=str(user.pk),
            object_repr=str(user),
            ip_address=ip,
        )


@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    ip = _get_client_ip(request) if request else None
    ActivityLog.objects.create(
        user=None,
        action="login_failed",
        object_type="accounts.User",
        details={"username": credentials.get("username", "")},
        ip_address=ip,
    )


def _get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
