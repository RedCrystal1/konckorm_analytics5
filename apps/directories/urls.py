from django.urls import path

from . import views

app_name = "directories"

urlpatterns = [
    path("nomenclature/", views.nomenclature_list_view, name="nomenclature_list"),
    path("nomenclature/create/", views.nomenclature_create_view, name="nomenclature_create"),
    path("nomenclature/<int:pk>/edit/", views.nomenclature_edit_view, name="nomenclature_edit"),
    path("departments/", views.department_list_view, name="department_list"),
    path("departments/create/", views.department_create_view, name="department_create"),
    path("departments/<int:pk>/edit/", views.department_edit_view, name="department_edit"),
]
