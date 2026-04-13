import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.directories.models import Department, Nomenclature


@pytest.fixture
def admin_client(db):
    user = User.objects.create_user(
        username="dir_admin", password="dirpass123456", role=User.Role.ADMIN
    )
    client = Client()
    client.login(username="dir_admin", password="dirpass123456")
    return client


@pytest.mark.django_db
class TestDepartmentModel:
    def test_str(self):
        dept = Department.objects.create(code="TST", name="Тестовый отдел")
        assert str(dept) == "Тестовый отдел"

    def test_hierarchy(self):
        parent = Department.objects.create(code="P", name="Родитель")
        child = Department.objects.create(code="C", name="Потомок", parent=parent)
        assert child.parent == parent
        assert parent.children.count() == 1


@pytest.mark.django_db
class TestNomenclatureModel:
    def test_str(self):
        nom = Nomenclature.objects.create(code="N01", name="Тест", kind="raw", unit="кг")
        assert "N01" in str(nom)
        assert "Тест" in str(nom)


@pytest.mark.django_db
class TestDirectoryViews:
    def test_nomenclature_list(self, admin_client):
        response = admin_client.get(reverse("directories:nomenclature_list"))
        assert response.status_code == 200

    def test_department_list(self, admin_client):
        response = admin_client.get(reverse("directories:department_list"))
        assert response.status_code == 200

    def test_procurement_cannot_access(self, db):
        user = User.objects.create_user(
            username="proc", password="procpass12345", role=User.Role.PROCUREMENT
        )
        client = Client()
        client.login(username="proc", password="procpass12345")
        response = client.get(reverse("directories:nomenclature_list"))
        assert response.status_code == 403
