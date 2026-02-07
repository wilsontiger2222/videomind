# tests/test_admin.py
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.models import create_user, create_job, update_job_status

TEST_DB = "./data/test_admin.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    from app.middleware.rate_limit import _request_log
    _request_log.clear()
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


@patch("app.services.health.psutil.virtual_memory")
@patch("app.services.health.psutil.cpu_percent")
@patch("app.services.health.psutil.disk_usage")
def test_admin_stats_returns_data(mock_disk, mock_cpu, mock_mem):
    mock_disk.return_value = MagicMock(percent=45.0)
    mock_cpu.return_value = 30.0
    mock_mem.return_value = MagicMock(percent=60.0)

    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        with patch("app.routers.admin.DATABASE_URL", TEST_DB):
            result = create_user(TEST_DB, email="admin@test.com", password="securepass123")
            from app.models import update_user_plan
            update_user_plan(TEST_DB, result["api_key"], plan="business")

            response = client.get(
                "/api/v1/admin/stats",
                headers={"Authorization": f"Bearer {result['api_key']}"}
            )

    assert response.status_code == 200
    data = response.json()
    assert "health" in data
    assert "stats" in data
    assert data["health"]["status"] == "healthy"


def test_admin_stats_requires_auth():
    response = client.get("/api/v1/admin/stats")
    assert response.status_code == 401


def test_admin_stats_with_legacy_key():
    with patch("app.routers.admin.DATABASE_URL", TEST_DB):
        with patch("app.services.health.psutil.disk_usage") as mock_disk:
            with patch("app.services.health.psutil.cpu_percent", return_value=30.0):
                with patch("app.services.health.psutil.virtual_memory") as mock_mem:
                    mock_disk.return_value = MagicMock(percent=45.0)
                    mock_mem.return_value = MagicMock(percent=60.0)

                    response = client.get(
                        "/api/v1/admin/stats",
                        headers={"Authorization": "Bearer test-key-123"}
                    )
    assert response.status_code == 200
