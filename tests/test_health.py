# tests/test_health.py
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from app.database import init_db
from app.models import create_job, update_job_status
from app.services.health import check_stuck_jobs, check_disk_usage, check_system_health

TEST_DB = "./data/test_health.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_check_stuck_jobs_finds_old_processing_jobs():
    job_id = create_job(TEST_DB, "https://youtube.com/test", {})
    update_job_status(TEST_DB, job_id, status="processing", progress=50)
    from app.database import get_connection
    conn = get_connection(TEST_DB)
    conn.execute(
        "UPDATE jobs SET created_at = datetime('now', '-20 minutes') WHERE id = ?",
        (job_id,)
    )
    conn.commit()
    conn.close()

    stuck = check_stuck_jobs(TEST_DB, max_minutes=10)
    assert len(stuck) == 1
    assert stuck[0]["id"] == job_id


def test_check_stuck_jobs_ignores_recent_jobs():
    job_id = create_job(TEST_DB, "https://youtube.com/test", {})
    update_job_status(TEST_DB, job_id, status="processing", progress=50)
    stuck = check_stuck_jobs(TEST_DB, max_minutes=10)
    assert len(stuck) == 0


def test_check_stuck_jobs_ignores_completed_jobs():
    job_id = create_job(TEST_DB, "https://youtube.com/test", {})
    update_job_status(TEST_DB, job_id, status="completed", progress=100)
    from app.database import get_connection
    conn = get_connection(TEST_DB)
    conn.execute(
        "UPDATE jobs SET created_at = datetime('now', '-20 minutes') WHERE id = ?",
        (job_id,)
    )
    conn.commit()
    conn.close()

    stuck = check_stuck_jobs(TEST_DB, max_minutes=10)
    assert len(stuck) == 0


@patch("app.services.health.psutil.disk_usage")
def test_check_disk_usage(mock_disk):
    mock_disk.return_value = MagicMock(percent=75.5)
    result = check_disk_usage()
    assert result["disk_percent"] == 75.5
    assert result["warning"] is False


@patch("app.services.health.psutil.disk_usage")
def test_check_disk_usage_warning(mock_disk):
    mock_disk.return_value = MagicMock(percent=92.0)
    result = check_disk_usage()
    assert result["disk_percent"] == 92.0
    assert result["warning"] is True


@patch("app.services.health.psutil.virtual_memory")
@patch("app.services.health.psutil.cpu_percent")
@patch("app.services.health.psutil.disk_usage")
def test_check_system_health(mock_disk, mock_cpu, mock_mem):
    mock_disk.return_value = MagicMock(percent=45.0)
    mock_cpu.return_value = 30.0
    mock_mem.return_value = MagicMock(percent=60.0)

    health = check_system_health(TEST_DB)
    assert health["status"] == "healthy"
    assert health["disk_percent"] == 45.0
    assert health["cpu_percent"] == 30.0
    assert health["memory_percent"] == 60.0
    assert health["stuck_jobs"] == 0
