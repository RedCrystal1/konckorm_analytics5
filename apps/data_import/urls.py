from django.urls import path

from . import views

app_name = "data_import"

urlpatterns = [
    path("", views.import_upload_view, name="upload"),
    path("<int:pk>/results/", views.import_results_view, name="results"),
    path("<int:pk>/duplicates/", views.duplicate_review_view, name="duplicates"),
    path("<int:pk>/corrections/", views.manual_correction_view, name="corrections"),
    path("history/", views.import_history_view, name="history"),
    # HTMX
    path("htmx/upload-progress/<int:pk>/", views.htmx_upload_progress, name="htmx_progress"),
]
