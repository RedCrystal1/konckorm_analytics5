from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "type", "severity", "is_read", "is_email_sent", "created_at"]
    list_filter = ["type", "severity", "is_read", "is_email_sent"]
    search_fields = ["title", "message", "user__username"]
    date_hierarchy = "created_at"
    readonly_fields = ["created_at", "read_at"]
