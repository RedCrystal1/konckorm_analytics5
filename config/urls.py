from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.api.urls", namespace="api")),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("", include("apps.dashboard.urls", namespace="dashboard")),
    path(
        "counterparties/",
        include("apps.counterparties.urls", namespace="counterparties"),
    ),
    path("directories/", include("apps.directories.urls", namespace="directories")),
    path("documents/", include("apps.documents.urls", namespace="documents")),
    path("registers/", include("apps.registers.urls", namespace="registers")),
    path("analytics/", include("apps.analytics.urls", namespace="analytics")),
    path("payments/", include("apps.payments.urls", namespace="payments")),
    path(
        "reconciliation/",
        include("apps.reconciliation.urls", namespace="reconciliation"),
    ),
    path("reports/", include("apps.reports.urls", namespace="reports")),
    path("import/", include("apps.data_import.urls", namespace="data_import")),
    path(
        "notifications/",
        include("apps.notifications.urls", namespace="notifications"),
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    try:
        import debug_toolbar

        urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    except ImportError:
        pass
