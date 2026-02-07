# tests/test_rate_limit.py
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.models import create_user

TEST_DB = "./data/test_rate_limit.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    # Clear the rate limit log between tests
    from app.middleware.rate_limit import _request_log
    _request_log.clear()
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


def test_rate_limit_allows_normal_requests():
    result = create_user(TEST_DB, email="normal@example.com", password="securepass123")
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        response = client.get(
            "/api/v1/health",
            headers={"Authorization": f"Bearer {result['api_key']}"}
        )
    assert response.status_code == 200


def test_rate_limit_blocks_after_exceeding_limit():
    result = create_user(TEST_DB, email="limited@example.com", password="securepass123")
    # Free plan = 10 requests/hour. Send 11 requests.
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        with patch("app.middleware.rate_limit.DATABASE_URL", TEST_DB):
            for i in range(10):
                response = client.get(
                    "/api/v1/health",
                    headers={"Authorization": f"Bearer {result['api_key']}"}
                )
                assert response.status_code == 200

            response = client.get(
                "/api/v1/health",
                headers={"Authorization": f"Bearer {result['api_key']}"}
            )
            assert response.status_code == 429
            assert "Rate limit exceeded" in response.json()["detail"]


def test_rate_limit_skips_public_paths():
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_rate_limit_skips_legacy_keys():
    # Legacy keys get business-tier limits (500/hr), so they shouldn't be rate limited easily
    for i in range(15):
        response = client.get(
            "/api/v1/health",
            headers={"Authorization": "Bearer test-key-123"}
        )
        assert response.status_code == 200
