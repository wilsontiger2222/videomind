# tests/test_report.py
import os
import pytest
from unittest.mock import patch, MagicMock
from app.database import init_db
from app.models import create_user, create_job, update_job_status
from app.services.report import generate_daily_stats, format_daily_report

TEST_DB = "./data/test_report.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_generate_daily_stats_empty_db():
    stats = generate_daily_stats(TEST_DB)
    assert stats["total_users"] == 0
    assert stats["total_jobs"] == 0
    assert stats["completed_jobs"] == 0
    assert stats["failed_jobs"] == 0


def test_generate_daily_stats_with_data():
    create_user(TEST_DB, email="user1@example.com", password="securepass123")
    create_user(TEST_DB, email="user2@example.com", password="securepass123")

    job1 = create_job(TEST_DB, "https://youtube.com/1", {})
    update_job_status(TEST_DB, job1, status="completed", progress=100)
    job2 = create_job(TEST_DB, "https://youtube.com/2", {})
    update_job_status(TEST_DB, job2, status="completed", progress=100)
    job3 = create_job(TEST_DB, "https://youtube.com/3", {})
    update_job_status(TEST_DB, job3, status="failed", error_message="timeout")

    stats = generate_daily_stats(TEST_DB)
    assert stats["total_users"] == 2
    assert stats["total_jobs"] == 3
    assert stats["completed_jobs"] == 2
    assert stats["failed_jobs"] == 1


def test_generate_daily_stats_plan_breakdown():
    from app.models import update_user_plan
    u1 = create_user(TEST_DB, email="free@example.com", password="securepass123")
    u2 = create_user(TEST_DB, email="pro@example.com", password="securepass123")
    update_user_plan(TEST_DB, u2["api_key"], plan="pro")
    u3 = create_user(TEST_DB, email="biz@example.com", password="securepass123")
    update_user_plan(TEST_DB, u3["api_key"], plan="business")

    stats = generate_daily_stats(TEST_DB)
    assert stats["users_by_plan"]["free"] == 1
    assert stats["users_by_plan"]["pro"] == 1
    assert stats["users_by_plan"]["business"] == 1


@patch("app.services.report.psutil.cpu_percent", return_value=35.0)
@patch("app.services.report.psutil.virtual_memory")
@patch("app.services.report.psutil.disk_usage")
def test_format_daily_report(mock_disk, mock_mem, mock_cpu):
    mock_disk.return_value = MagicMock(percent=42.0)
    mock_mem.return_value = MagicMock(percent=58.0)

    stats = generate_daily_stats(TEST_DB)
    report = format_daily_report(stats)

    assert "VideoMind Daily Report" in report
    assert "USERS:" in report
    assert "JOBS:" in report
    assert "SERVER:" in report
