import logging

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("apps.accounts")


class ActivityLogMiddleware(MiddlewareMixin):
    """Middleware для логирования активности пользователей.

    Логирует POST/PUT/PATCH/DELETE запросы аутентифицированных пользователей.
    """

    TRACKED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")

    def process_view(self, request, view_func, view_args, view_kwargs):
        if (
            request.method in self.TRACKED_METHODS
            and hasattr(request, "user")
            and request.user.is_authenticated
        ):
            # Lazy import to avoid circular dependencies
            from apps.accounts.models import ActivityLog

            try:
                ActivityLog.objects.create(
                    user=request.user,
                    action=f"{request.method} {request.path}",
                    object_type=getattr(view_func, "__module__", ""),
                    ip_address=self.get_client_ip(request),
                )
            except Exception:
                logger.exception("Failed to log activity")

        return None
