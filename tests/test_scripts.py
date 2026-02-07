# tests/test_scripts.py
import os
import pytest
from unittest.mock import patch, MagicMock
from app.database import init_db

TEST_DB = "./data/test_scripts.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@patch("app.services.health.psutil.virtual_memory")
@patch("app.services.health.psutil.cpu_percent")
@patch("app.services.health.psutil.disk_usage")
def test_health_check_script_runs(mock_disk, mock_cpu, mock_mem):
    mock_disk.return_value = MagicMock(percent=45.0)
    mock_cpu.return_value = 30.0
    mock_mem.return_value = MagicMock(percent=60.0)

    from scripts.health_check import run_health_check
    result = run_health_check(TEST_DB)
    assert result["status"] == "healthy"


def test_cleanup_script_runs():
    from scripts.cleanup import run_cleanup
    result = run_cleanup(
        temp_dir="./data/test_temp_scripts",
        frames_dir="./data/test_frames_scripts"
    )
    assert "temp" in result
    assert "frames" in result


@patch("app.services.report.psutil.cpu_percent", return_value=30.0)
@patch("app.services.report.psutil.virtual_memory")
@patch("app.services.report.psutil.disk_usage")
@patch("app.services.email_utils.send_email")
def test_daily_report_script_runs(mock_send, mock_disk, mock_mem, mock_cpu):
    mock_disk.return_value = MagicMock(percent=42.0)
    mock_mem.return_value = MagicMock(percent=58.0)
    mock_send.return_value = {"status": "skipped", "reason": "No API key"}

    from scripts.daily_report import run_daily_report
    result = run_daily_report(TEST_DB)
    assert "stats" in result
    assert "report" in result
