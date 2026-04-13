import pytest
from django.test import Client, RequestFactory
from django.core.exceptions import PermissionDenied

from apps.accounts.decorators import admin_required, role_required
from apps.accounts.models import User


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.mark.django_db
class TestRoleRequired:
    def test_admin_required_passes_for_admin(self, rf):
        user = User.objects.create_user(
            username="adm", password="pass1234567", role=User.Role.ADMIN
        )

        @admin_required
        def dummy_view(request):
            from django.http import HttpResponse
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user
        response = dummy_view(request)
        assert response.status_code == 200

    def test_admin_required_denies_accountant(self, rf):
        user = User.objects.create_user(
            username="acc", password="pass1234567", role=User.Role.ACCOUNTANT
        )

        @admin_required
        def dummy_view(request):
            from django.http import HttpResponse
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user
        with pytest.raises(PermissionDenied):
            dummy_view(request)

    def test_role_required_multiple_roles(self, rf):
        user = User.objects.create_user(
            username="mgr", password="pass1234567", role=User.Role.MANAGER
        )

        @role_required("admin", "manager")
        def dummy_view(request):
            from django.http import HttpResponse
            return HttpResponse("ok")

        request = rf.get("/")
        request.user = user
        response = dummy_view(request)
        assert response.status_code == 200
