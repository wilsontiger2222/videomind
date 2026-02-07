# tests/test_usage_endpoint.py
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.models import create_user, increment_user_video_count

TEST_DB = "./data/test_usage_endpoint.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


def test_usage_returns_plan_info():
    result = create_user(TEST_DB, email="usage@example.com", password="securepass123")
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        with patch("app.routers.usage.DATABASE_URL", TEST_DB):
            response = client.get(
                "/api/v1/usage",
                headers={"Authorization": f"Bearer {result['api_key']}"}
            )
    assert response.status_code == 200
    data = response.json()
    assert data["plan"] == "free"
    assert data["videos_today"] == 0
    assert data["videos_limit"] == 3
    assert data["requests_limit"] == 10


def test_usage_reflects_video_count():
    result = create_user(TEST_DB, email="count@example.com", password="securepass123")
    increment_user_video_count(TEST_DB, result["api_key"])
    increment_user_video_count(TEST_DB, result["api_key"])
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        with patch("app.routers.usage.DATABASE_URL", TEST_DB):
            response = client.get(
                "/api/v1/usage",
                headers={"Authorization": f"Bearer {result['api_key']}"}
            )
    assert response.status_code == 200
    assert response.json()["videos_today"] == 2


def test_usage_with_legacy_key():
    response = client.get(
        "/api/v1/usage",
        headers={"Authorization": "Bearer test-key-123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["plan"] == "business"
