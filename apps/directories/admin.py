from django.contrib import admin

from .models import Department, Nomenclature


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "parent", "is_active"]
    list_filter = ["is_active", "parent"]
    search_fields = ["name", "code"]


@admin.register(Nomenclature)
class NomenclatureAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "kind", "unit", "is_active"]
    list_filter = ["kind", "is_active"]
    search_fields = ["name", "code"]
