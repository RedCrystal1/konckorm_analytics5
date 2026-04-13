from django.contrib import admin

from .models import APIToken, SyncSession


@admin.register(APIToken)
class APITokenAdmin(admin.ModelAdmin):
    list_display = ["name", "key_short", "is_active", "last_used_at", "created_at"]
    list_filter = ["is_active"]
    readonly_fields = ["key", "last_used_at", "created_at"]

    def key_short(self, obj):
        return f"{obj.key[:8]}...{obj.key[-4:]}" if obj.key else "—"
    key_short.short_description = "Ключ"


@admin.register(SyncSession)
class SyncSessionAdmin(admin.ModelAdmin):
    list_display = [
        "id", "direction", "endpoint", "status",
        "records_received", "records_created", "records_updated", "records_errors",
        "started_at", "completed_at",
    ]
    list_filter = ["direction", "status"]
    readonly_fields = [
        "direction", "endpoint", "status", "api_token",
        "records_received", "records_created", "records_updated", "records_errors",
        "error_message", "details", "started_at", "completed_at",
    ]
    date_hierarchy = "started_at"

    def has_add_permission(self, request):
        return False
