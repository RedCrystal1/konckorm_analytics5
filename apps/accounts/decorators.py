from functools import wraps

from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required


def role_required(*roles):
    """Декоратор проверки роли пользователя.

    Использование:
        @role_required('admin', 'accountant')
        def my_view(request):
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied(
                    "У вас нет прав для доступа к этой странице."
                )
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def admin_required(view_func):
    """Только для администраторов."""
    return role_required("admin")(view_func)


def accountant_or_admin_required(view_func):
    """Для бухгалтеров и администраторов."""
    return role_required("admin", "accountant")(view_func)


def manager_or_above_required(view_func):
    """Для руководителей, бухгалтеров и администраторов."""
    return role_required("admin", "accountant", "manager")(view_func)
