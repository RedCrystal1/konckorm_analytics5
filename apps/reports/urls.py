from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_generator_view, name="generator"),
    path("history/", views.report_history_view, name="history"),
    path("download/<int:pk>/", views.report_download, name="download"),
]
