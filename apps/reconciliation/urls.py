from django.urls import path

from . import views

app_name = "reconciliation"

urlpatterns = [
    path("", views.discrepancy_list_view, name="discrepancy_list"),
    path("<int:pk>/", views.discrepancy_detail_view, name="discrepancy_detail"),
    path("<int:pk>/update-status/", views.discrepancy_update_status, name="update_status"),
    path("generate-act/", views.generate_reconciliation_act_view, name="generate_act"),
    path("acts/<int:pk>/", views.reconciliation_act_detail_view, name="act_detail"),
]
