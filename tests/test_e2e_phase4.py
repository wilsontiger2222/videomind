# tests/test_e2e_phase4.py
import os
import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.models import create_user, create_job, update_job_status, update_user_plan

TEST_DB = "./data/test_e2e_phase4.db"
TEST_TEMP = "./data/test_e2e_temp"
TEST_FRAMES = "./data/test_e2e_frames"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    os.makedirs(TEST_TEMP, exist_ok=True)
    os.makedirs(TEST_FRAMES, exist_ok=True)
    init_db(TEST_DB)
    from app.middleware.rate_limit import _request_log
    _request_log.clear()
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    for d in [TEST_TEMP, TEST_FRAMES]:
        if os.path.exists(d):
            for root, dirs, files in os.walk(d, topdown=False):
                for f in files:
                    os.remove(os.path.join(root, f))
                for dd in dirs:
                    os.rmdir(os.path.join(root, dd))
            if os.path.exists(d):
                os.rmdir(d)

client = TestClient(app)


@patch("app.services.health.psutil.virtual_memory")
@patch("app.services.health.psutil.cpu_percent")
@patch("app.services.health.psutil.disk_usage")
@patch("app.services.report.psutil.virtual_memory")
@patch("app.services.report.psutil.cpu_percent")
@patch("app.services.report.psutil.disk_usage")
def test_full_phase4_operations_lifecycle(
    mock_report_disk, mock_report_cpu, mock_report_mem,
    mock_health_disk, mock_health_cpu, mock_health_mem
):
    """Test: health check -> cleanup -> report -> admin stats"""

    # Mock system metrics
    for mock_disk in [mock_health_disk, mock_report_disk]:
        mock_disk.return_value = MagicMock(percent=45.0)
    for mock_cpu in [mock_health_cpu, mock_report_cpu]:
        mock_cpu.return_value = 30.0
    for mock_mem in [mock_health_mem, mock_report_mem]:
        mock_mem.return_value = MagicMock(percent=60.0)

    # Step 1: Create some data
    user = create_user(TEST_DB, email="e2e4@example.com", password="securepass123")
    update_user_plan(TEST_DB, user["api_key"], plan="business")
    job_id = create_job(TEST_DB, "https://youtube.com/test", {})
    update_job_status(TEST_DB, job_id, status="completed", progress=100)

    # Step 2: Run health check
    from scripts.health_check import run_health_check
    health = run_health_check(TEST_DB)
    assert health["status"] == "healthy"
    assert health["stuck_jobs"] == 0

    # Step 3: Create old temp file and run cleanup
    old_file = os.path.join(TEST_TEMP, "old.mp4")
    with open(old_file, "w") as f:
        f.write("old")
    old_time = time.time() - 7200
    os.utime(old_file, (old_time, old_time))

    from scripts.cleanup import run_cleanup
    cleanup = run_cleanup(temp_dir=TEST_TEMP, frames_dir=TEST_FRAMES)
    assert cleanup["temp"]["deleted"] == 1
    assert not os.path.exists(old_file)

    # Step 4: Generate daily report
    from scripts.daily_report import run_daily_report
    with patch("app.services.email_utils.send_email") as mock_send:
        mock_send.return_value = {"status": "skipped", "reason": "No API key"}
        report = run_daily_report(TEST_DB)
    assert report["stats"]["total_users"] == 1
    assert report["stats"]["completed_jobs"] == 1
    assert "VideoMind Daily Report" in report["report"]

    # Step 5: Hit admin stats endpoint
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        with patch("app.routers.admin.DATABASE_URL", TEST_DB):
            response = client.get(
                "/api/v1/admin/stats",
                headers={"Authorization": f"Bearer {user['api_key']}"}
            )
    assert response.status_code == 200
    data = response.json()
    assert data["health"]["status"] == "healthy"
    assert data["stats"]["total_users"] == 1
