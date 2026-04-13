import json

import pytest
from django.test import Client

from apps.api.models import APIToken


@pytest.fixture
def api_token(db):
    return APIToken.objects.create(
        name="Тест 1С",
        key="test_token_key_1234567890abcdef1234567890abcdef",
        is_active=True,
    )


@pytest.fixture
def api_client(api_token):
    client = Client()
    client.defaults["HTTP_AUTHORIZATION"] = f"Token {api_token.key}"
    return client


@pytest.mark.django_db
class TestAPIAuth:
    def test_no_token_returns_401(self):
        client = Client()
        response = client.get("/api/v1/status/")
        assert response.status_code == 401

    def test_invalid_token_returns_403(self):
        client = Client()
        client.defaults["HTTP_AUTHORIZATION"] = "Token invalid_key"
        response = client.get("/api/v1/status/")
        assert response.status_code == 403

    def test_valid_token_returns_200(self, api_client):
        response = api_client.get("/api/v1/status/")
        assert response.status_code == 200

    def test_docs_no_auth_required(self):
        client = Client()
        response = client.get("/api/v1/")
        assert response.status_code == 200


@pytest.mark.django_db
class TestSyncCounterparties:
    def test_sync_creates_counterparty(self, api_client):
        data = {
            "counterparties": [
                {
                    "code": "API-001",
                    "name": "Тест АПИ",
                    "inn": "1234567890",
                }
            ]
        }
        response = api_client.post(
            "/api/v1/sync/counterparties/",
            json.dumps(data),
            content_type="application/json",
        )
        assert response.status_code == 200
        body = response.json()
        assert body["created"] == 1

    def test_sync_updates_counterparty(self, api_client):
        # Создаём
        data = {"counterparties": [{"code": "API-002", "name": "Старое имя", "inn": "9999999999"}]}
        api_client.post("/api/v1/sync/counterparties/", json.dumps(data), content_type="application/json")

        # Обновляем
        data["counterparties"][0]["name"] = "Новое имя"
        response = api_client.post("/api/v1/sync/counterparties/", json.dumps(data), content_type="application/json")
        body = response.json()
        assert body["updated"] == 1

        from apps.counterparties.models import Counterparty
        cp = Counterparty.objects.get(code_1c="API-002")
        assert cp.name == "Новое имя"


@pytest.mark.django_db
class TestExportEndpoints:
    def test_export_reconciliations(self, api_client):
        response = api_client.get("/api/v1/export/reconciliations/")
        assert response.status_code == 200
        assert "reconciliations" in response.json()

    def test_export_debt_status(self, api_client):
        response = api_client.get("/api/v1/export/debt-status/")
        assert response.status_code == 200
        assert "debt_records" in response.json()

    def test_export_payment_recommendations(self, api_client):
        response = api_client.get("/api/v1/export/payment-recommendations/")
        assert response.status_code == 200
        assert "recommendations" in response.json()
