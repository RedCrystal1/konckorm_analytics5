from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/edit/", views.profile_edit_view, name="profile_edit"),
    path("users/", views.user_list_view, name="user_list"),
    path("users/create/", views.user_create_view, name="user_create"),
    path("users/<uuid:pk>/edit/", views.user_update_view, name="user_edit"),
    path("users/<uuid:pk>/delete/", views.user_delete_view, name="user_delete"),
    path("audit-log/", views.audit_log_view, name="audit_log"),
]
