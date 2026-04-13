import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.data_import.models import ImportSession
from apps.data_import.validators import calculate_checksum


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user(
        username="imp_admin", password="imppass123456", role=User.Role.ADMIN
    )
    client = Client()
    client.login(username="imp_admin", password="imppass123456")
    return client


@pytest.mark.django_db
class TestImportSession:
    def test_progress_percent_zero(self):
        session = ImportSession(total_records=0, processed_records=0)
        assert session.progress_percent == 0

    def test_progress_percent(self):
        session = ImportSession(total_records=100, processed_records=50)
        assert session.progress_percent == 50

    def test_str(self, db):
        user = User.objects.create_user(username="x", password="pass1234567")
        session = ImportSession.objects.create(
            mode="initial",
            file_format="excel",
            uploaded_file="test.xlsx",
            initiated_by=user,
        )
        assert f"#{session.pk}" in str(session)


@pytest.mark.django_db
class TestImportViews:
    def test_upload_page(self, admin_client):
        response = admin_client.get(reverse("data_import:upload"))
        assert response.status_code == 200

    def test_history_page(self, admin_client):
        response = admin_client.get(reverse("data_import:history"))
        assert response.status_code == 200

    def test_procurement_cannot_access(self, db):
        User.objects.create_user(
            username="proc", password="procpass12345", role=User.Role.PROCUREMENT
        )
        client = Client()
        client.login(username="proc", password="procpass12345")
        response = client.get(reverse("data_import:upload"))
        assert response.status_code == 403
