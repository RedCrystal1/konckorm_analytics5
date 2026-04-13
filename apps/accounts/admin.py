from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import ActivityLog, User, UserCounterpartyAccess


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        "username",
        "last_name",
        "first_name",
        "role",
        "department",
        "is_active",
    ]
    list_filter = ["role", "is_active", "department"]
    search_fields = ["username", "first_name", "last_name", "email"]
    ordering = ["last_name", "first_name"]

    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Дополнительно",
            {
                "fields": (
                    "role",
                    "patronymic",
                    "department",
                    "phone",
                    "position",
                    "is_two_factor_enabled",
                )
            },
        ),
        (
            "Уведомления",
            {
                "fields": (
                    "notify_overdue",
                    "notify_cash_gap",
                    "notify_import",
                )
            },
        ),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Роль и подразделение",
            {
                "fields": ("role", "department"),
            },
        ),
    )


@admin.register(UserCounterpartyAccess)
class UserCounterpartyAccessAdmin(admin.ModelAdmin):
    list_display = ["user", "counterparty"]
    list_filter = ["user"]
    search_fields = ["user__username", "counterparty__name"]


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "user", "action", "object_type", "ip_address"]
    list_filter = ["action", "object_type"]
    search_fields = ["user__username", "object_repr"]
    readonly_fields = [
        "user",
        "action",
        "object_type",
        "object_id",
        "object_repr",
        "details",
        "ip_address",
        "timestamp",
    ]
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
