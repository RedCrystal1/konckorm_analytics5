from django.contrib import admin

from .models import DuplicateCandidate, ImportLog, ImportSession


class ImportLogInline(admin.TabularInline):
    model = ImportLog
    extra = 0
    readonly_fields = ["level", "message", "row_number", "object_type", "timestamp"]


@admin.register(ImportSession)
class ImportSessionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "mode",
        "file_format",
        "status",
        "total_records",
        "created_records",
        "error_records",
        "duplicates_found",
        "initiated_by",
        "created_at",
    ]
    list_filter = ["status", "mode", "file_format"]
    readonly_fields = [
        "total_records",
        "processed_records",
        "created_records",
        "updated_records",
        "error_records",
        "checksum",
        "duplicates_found",
        "started_at",
        "completed_at",
    ]
    inlines = [ImportLogInline]


@admin.register(DuplicateCandidate)
class DuplicateCandidateAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "existing_counterparty",
        "match_field",
        "match_confidence",
        "resolution",
    ]
    list_filter = ["resolution", "match_field"]
    raw_id_fields = ["existing_counterparty"]
