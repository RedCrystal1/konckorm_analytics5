from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView as BaseLoginView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from .decorators import admin_required
from .forms import LoginForm, ProfileForm, UserCreateForm, UserUpdateForm
from .models import ActivityLog, User


class CustomLoginView(BaseLoginView):
    """Страница входа."""

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


@login_required
def logout_view(request):
    """Выход из системы."""
    logout(request)
    return redirect("accounts:login")


@login_required
def profile_view(request):
    """Просмотр профиля."""
    return render(request, "accounts/profile.html", {"user_obj": request.user})


@login_required
def profile_edit_view(request):
    """Редактирование профиля."""
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль успешно обновлён.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile_edit.html", {"form": form})


@admin_required
def user_list_view(request):
    """Список пользователей (только для администратора)."""
    users = User.objects.select_related("department").all()
    role_filter = request.GET.get("role")
    if role_filter:
        users = users.filter(role=role_filter)
    search = request.GET.get("search", "").strip()
    if search:
        users = users.filter(
            models_Q(last_name__icontains=search)
            | models_Q(first_name__icontains=search)
            | models_Q(username__icontains=search)
        )
    return render(request, "accounts/user_list.html", {"users": users})


@admin_required
def user_create_view(request):
    """Создание пользователя."""
    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request, f"Пользователь {user.get_full_name()} создан."
            )
            return redirect("accounts:user_list")
    else:
        form = UserCreateForm()
    return render(request, "accounts/user_form.html", {"form": form, "title": "Создание пользователя"})


@admin_required
def user_update_view(request, pk):
    """Редактирование пользователя."""
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        form = UserUpdateForm(request.POST, instance=user_obj)
        if form.is_valid():
            form.save()
            messages.success(
                request, f"Пользователь {user_obj.get_full_name()} обновлён."
            )
            return redirect("accounts:user_list")
    else:
        form = UserUpdateForm(instance=user_obj)
    return render(
        request,
        "accounts/user_form.html",
        {"form": form, "title": "Редактирование пользователя", "user_obj": user_obj},
    )


@admin_required
def user_delete_view(request, pk):
    """Деактивация пользователя."""
    user_obj = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        user_obj.is_active = False
        user_obj.save(update_fields=["is_active"])
        messages.success(
            request, f"Пользователь {user_obj.get_full_name()} деактивирован."
        )
        return redirect("accounts:user_list")
    return render(request, "accounts/user_confirm_delete.html", {"user_obj": user_obj})


@admin_required
def audit_log_view(request):
    """Журнал аудита."""
    logs = ActivityLog.objects.select_related("user").all()[:500]
    return render(request, "accounts/audit_log.html", {"logs": logs})


# Helper
from django.db.models import Q as models_Q
