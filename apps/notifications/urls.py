from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list_view, name="list"),
    path("<int:pk>/", views.notification_detail_view, name="detail"),
    path("<int:pk>/read/", views.mark_as_read, name="mark_read"),
    path("<int:pk>/delete/", views.notification_delete, name="delete"),
    path("mark-all-read/", views.mark_all_read, name="mark_all_read"),
    path("delete-read/", views.delete_all_read, name="delete_read"),
    path("settings/", views.notification_settings_view, name="settings"),
    # HTMX
    path("htmx/dropdown/", views.htmx_notification_dropdown, name="htmx_dropdown"),
    path("htmx/count/", views.htmx_notification_count, name="htmx_count"),
]
