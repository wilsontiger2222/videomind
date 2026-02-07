# tests/test_auth.py
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.models import create_user

TEST_DB = "./data/test_auth2.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


def test_request_without_api_key_is_rejected():
    response = client.post("/api/v1/analyze", json={"url": "https://youtube.com/watch?v=test"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing API key"


def test_request_with_invalid_api_key_is_rejected():
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        response = client.post(
            "/api/v1/analyze",
            json={"url": "https://youtube.com/watch?v=test"},
            headers={"Authorization": "Bearer sk_invalid_key"}
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


def test_request_with_valid_db_api_key_passes():
    result = create_user(TEST_DB, email="auth@example.com", password="securepass123")
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        response = client.get(
            "/api/v1/health",
            headers={"Authorization": f"Bearer {result['api_key']}"}
        )
    assert response.status_code == 200


def test_request_with_legacy_env_api_key_passes():
    response = client.get(
        "/api/v1/health",
        headers={"Authorization": "Bearer test-key-123"}
    )
    assert response.status_code == 200


def test_health_endpoint_works_without_key():
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_register_works_without_key():
    with patch("app.routers.auth.DATABASE_URL", TEST_DB):
        response = client.post(
            "/api/v1/register",
            json={"email": "nokey@example.com", "password": "securepass123"}
        )
    assert response.status_code == 200
