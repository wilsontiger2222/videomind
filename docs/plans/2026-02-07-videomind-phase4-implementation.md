# VideoMind API — Phase 4 Implementation Plan (Autonomy + Polish)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add structured logging, health checks, temp file cleanup, email reports, admin stats endpoint, and cron-ready CLI scripts to make the VideoMind API self-monitoring and self-healing.

**Architecture:** Structured Python logging replaces silent error swallowing. Service modules handle health checks, cleanup, and reporting. A SendGrid wrapper sends daily report emails. CLI scripts in `scripts/` provide cron entry points. An admin stats endpoint exposes system health via API.

**Tech Stack:** Python 3.14, FastAPI, SQLite, logging (stdlib), sendgrid, shutil, psutil

---

### Task 1: Add Dependencies + Logging Config

**Files:**
- Modify: `videomind/requirements.txt`
- Create: `videomind/app/logging_config.py`
- Create: `videomind/tests/test_logging_config.py`

**Step 1: Update requirements.txt**

Add these lines to the end of `videomind/requirements.txt`:

```
sendgrid
psutil
```

**Step 2: Install new dependencies**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pip install sendgrid psutil`
Expected: Successful install

**Step 3: Update requirements.txt with installed versions**

Update the `sendgrid` and `psutil` lines with the installed versions (e.g., `sendgrid==6.x.x`, `psutil==6.x.x`).

**Step 4: Add SENDGRID_API_KEY and ADMIN_EMAIL to config.py**

In `videomind/app/config.py`, add after the existing Stripe config lines:

```python
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@videomind.ai")
```

**Step 5: Write the failing test**

```python
# tests/test_logging_config.py
import logging
from app.logging_config import setup_logging


def test_setup_logging_returns_logger():
    logger = setup_logging("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"


def test_logger_has_handler():
    logger = setup_logging("test_handler")
    assert len(logger.handlers) > 0


def test_logger_level_is_info():
    logger = setup_logging("test_level")
    assert logger.level == logging.INFO
```

**Step 6: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_logging_config.py -v`
Expected: FAIL — module doesn't exist

**Step 7: Write logging_config.py**

```python
# app/logging_config.py
import logging
import sys


def setup_logging(name: str, level=logging.INFO) -> logging.Logger:
    """Create and configure a logger with consistent formatting."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
```

**Step 8: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_logging_config.py -v`
Expected: ALL PASS

**Step 9: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL 78 PASS + 3 new = 81

---

### Task 2: Health Check Service

**Files:**
- Create: `videomind/app/services/health.py`
- Create: `videomind/tests/test_health.py`

**Step 1: Write the failing test**

```python
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
    # Manually set created_at to 20 minutes ago
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
    # This job was just created (< 10 minutes), should not be stuck
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
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_health.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write health.py**

```python
# app/services/health.py
import psutil
from app.database import get_connection
from app.logging_config import setup_logging

logger = setup_logging("health")


def check_stuck_jobs(db_path, max_minutes=10):
    """Find jobs stuck in 'processing' for longer than max_minutes."""
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT id, url, status, progress, step, created_at
           FROM jobs
           WHERE status = 'processing'
           AND created_at < datetime('now', ? || ' minutes')""",
        (f"-{max_minutes}",)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def check_disk_usage(path="/"):
    """Check disk usage and return warning if above 85%."""
    usage = psutil.disk_usage(path)
    return {
        "disk_percent": usage.percent,
        "warning": usage.percent > 85,
    }


def check_system_health(db_path, disk_path="/"):
    """Run all health checks and return a summary."""
    stuck = check_stuck_jobs(db_path)
    disk = check_disk_usage(disk_path)
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()

    status = "healthy"
    if disk["warning"] or mem.percent > 90 or len(stuck) > 0:
        status = "degraded"

    return {
        "status": status,
        "disk_percent": disk["disk_percent"],
        "cpu_percent": cpu,
        "memory_percent": mem.percent,
        "stuck_jobs": len(stuck),
        "stuck_job_ids": [j["id"] for j in stuck],
    }
```

**Step 4: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_health.py -v`
Expected: ALL PASS

**Step 5: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

---

### Task 3: Temp File Cleanup Service

**Files:**
- Create: `videomind/app/services/cleanup.py`
- Create: `videomind/tests/test_cleanup.py`

**Step 1: Write the failing test**

```python
# tests/test_cleanup.py
import os
import time
import pytest
from app.services.cleanup import cleanup_temp_files, cleanup_old_frames

TEMP_DIR = "./data/test_temp_cleanup"
FRAMES_DIR = "./data/test_frames_cleanup"


@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(FRAMES_DIR, exist_ok=True)
    yield
    # Clean up dirs
    for d in [TEMP_DIR, FRAMES_DIR]:
        if os.path.exists(d):
            for root, dirs, files in os.walk(d, topdown=False):
                for f in files:
                    os.remove(os.path.join(root, f))
                for dd in dirs:
                    os.rmdir(os.path.join(root, dd))
            os.rmdir(d)


def test_cleanup_temp_files_removes_old_files():
    # Create a file and make it appear old
    old_file = os.path.join(TEMP_DIR, "old_video.mp4")
    with open(old_file, "w") as f:
        f.write("old data")
    # Set mtime to 2 hours ago
    old_time = time.time() - 7200
    os.utime(old_file, (old_time, old_time))

    result = cleanup_temp_files(TEMP_DIR, max_age_seconds=3600)
    assert result["deleted"] == 1
    assert not os.path.exists(old_file)


def test_cleanup_temp_files_keeps_recent_files():
    recent_file = os.path.join(TEMP_DIR, "recent_video.mp4")
    with open(recent_file, "w") as f:
        f.write("recent data")

    result = cleanup_temp_files(TEMP_DIR, max_age_seconds=3600)
    assert result["deleted"] == 0
    assert os.path.exists(recent_file)


def test_cleanup_old_frames_removes_old_dirs():
    old_job_dir = os.path.join(FRAMES_DIR, "job_old123")
    os.makedirs(old_job_dir, exist_ok=True)
    frame_file = os.path.join(old_job_dir, "frame_001.jpg")
    with open(frame_file, "w") as f:
        f.write("frame data")
    # Set mtime to 31 days ago
    old_time = time.time() - (31 * 86400)
    os.utime(frame_file, (old_time, old_time))
    os.utime(old_job_dir, (old_time, old_time))

    result = cleanup_old_frames(FRAMES_DIR, max_age_days=30)
    assert result["deleted_dirs"] == 1
    assert not os.path.exists(old_job_dir)


def test_cleanup_old_frames_keeps_recent_dirs():
    recent_dir = os.path.join(FRAMES_DIR, "job_recent")
    os.makedirs(recent_dir, exist_ok=True)
    frame_file = os.path.join(recent_dir, "frame_001.jpg")
    with open(frame_file, "w") as f:
        f.write("frame data")

    result = cleanup_old_frames(FRAMES_DIR, max_age_days=30)
    assert result["deleted_dirs"] == 0
    assert os.path.exists(recent_dir)


def test_cleanup_temp_handles_missing_dir():
    result = cleanup_temp_files("./data/nonexistent_dir", max_age_seconds=3600)
    assert result["deleted"] == 0
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_cleanup.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write cleanup.py**

```python
# app/services/cleanup.py
import os
import time
import shutil
from app.logging_config import setup_logging

logger = setup_logging("cleanup")


def cleanup_temp_files(temp_dir, max_age_seconds=3600):
    """Delete files in temp_dir older than max_age_seconds. Returns count of deleted files."""
    deleted = 0
    if not os.path.exists(temp_dir):
        return {"deleted": 0}

    now = time.time()
    for entry in os.listdir(temp_dir):
        path = os.path.join(temp_dir, entry)
        if os.path.isfile(path):
            mtime = os.path.getmtime(path)
            if now - mtime > max_age_seconds:
                try:
                    os.remove(path)
                    deleted += 1
                    logger.info(f"Deleted temp file: {path}")
                except OSError as e:
                    logger.warning(f"Failed to delete {path}: {e}")

    return {"deleted": deleted}


def cleanup_old_frames(frames_dir, max_age_days=30):
    """Delete frame directories older than max_age_days. Returns count of deleted dirs."""
    deleted_dirs = 0
    if not os.path.exists(frames_dir):
        return {"deleted_dirs": 0}

    now = time.time()
    max_age_seconds = max_age_days * 86400

    for entry in os.listdir(frames_dir):
        dir_path = os.path.join(frames_dir, entry)
        if os.path.isdir(dir_path):
            mtime = os.path.getmtime(dir_path)
            if now - mtime > max_age_seconds:
                try:
                    shutil.rmtree(dir_path)
                    deleted_dirs += 1
                    logger.info(f"Deleted old frames dir: {dir_path}")
                except OSError as e:
                    logger.warning(f"Failed to delete {dir_path}: {e}")

    return {"deleted_dirs": deleted_dirs}
```

**Step 4: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_cleanup.py -v`
Expected: ALL PASS

**Step 5: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

---

### Task 4: Email Utils (SendGrid)

**Files:**
- Create: `videomind/app/services/email_utils.py`
- Create: `videomind/tests/test_email_utils.py`

**Step 1: Write the failing test**

```python
# tests/test_email_utils.py
import pytest
from unittest.mock import patch, MagicMock
from app.services.email_utils import send_email


@patch("app.services.email_utils.SendGridAPIClient")
def test_send_email_success(mock_sg_class):
    mock_client = MagicMock()
    mock_response = MagicMock(status_code=202)
    mock_client.send.return_value = mock_response
    mock_sg_class.return_value = mock_client

    result = send_email(
        to_email="user@example.com",
        subject="Test Subject",
        body="Test body content"
    )

    assert result["status"] == "sent"
    assert result["status_code"] == 202
    mock_client.send.assert_called_once()


@patch("app.services.email_utils.SendGridAPIClient")
def test_send_email_failure(mock_sg_class):
    mock_client = MagicMock()
    mock_client.send.side_effect = Exception("API error")
    mock_sg_class.return_value = mock_client

    result = send_email(
        to_email="user@example.com",
        subject="Test Subject",
        body="Test body content"
    )

    assert result["status"] == "failed"
    assert "API error" in result["error"]


@patch("app.services.email_utils.SENDGRID_API_KEY", "")
def test_send_email_no_api_key():
    result = send_email(
        to_email="user@example.com",
        subject="Test",
        body="Body"
    )
    assert result["status"] == "skipped"
    assert "No SendGrid API key" in result["reason"]
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_email_utils.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write email_utils.py**

```python
# app/services/email_utils.py
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.config import SENDGRID_API_KEY, ADMIN_EMAIL
from app.logging_config import setup_logging

logger = setup_logging("email")


def send_email(to_email, subject, body, from_email=None):
    """Send an email via SendGrid. Returns status dict."""
    if not SENDGRID_API_KEY:
        logger.warning("No SendGrid API key configured, skipping email")
        return {"status": "skipped", "reason": "No SendGrid API key configured"}

    sender = from_email or f"noreply@videomind.ai"

    message = Mail(
        from_email=sender,
        to_emails=to_email,
        subject=subject,
        plain_text_content=body
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(f"Email sent to {to_email}: {subject} (status: {response.status_code})")
        return {"status": "sent", "status_code": response.status_code}
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return {"status": "failed", "error": str(e)}
```

**Step 4: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_email_utils.py -v`
Expected: ALL PASS

**Step 5: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

---

### Task 5: Daily Report Generator

**Files:**
- Create: `videomind/app/services/report.py`
- Create: `videomind/tests/test_report.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_report.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write report.py**

```python
# app/services/report.py
import psutil
from datetime import datetime
from app.database import get_connection
from app.logging_config import setup_logging

logger = setup_logging("report")


def generate_daily_stats(db_path):
    """Query the database for daily statistics."""
    conn = get_connection(db_path)

    # User counts
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    # Users by plan
    plan_rows = conn.execute(
        "SELECT plan, COUNT(*) as count FROM users GROUP BY plan"
    ).fetchall()
    users_by_plan = {row["plan"]: row["count"] for row in plan_rows}

    # Job counts
    total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    completed_jobs = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE status = 'completed'"
    ).fetchone()[0]
    failed_jobs = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE status = 'failed'"
    ).fetchone()[0]
    processing_jobs = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE status = 'processing'"
    ).fetchone()[0]

    conn.close()

    return {
        "total_users": total_users,
        "users_by_plan": users_by_plan,
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "processing_jobs": processing_jobs,
        "generated_at": datetime.now().isoformat(),
    }


def format_daily_report(stats):
    """Format stats into a human-readable daily report string."""
    disk = psutil.disk_usage("/")
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()

    date_str = datetime.now().strftime("%b %d, %Y")

    plan_breakdown = ", ".join(
        f"{plan}: {count}" for plan, count in stats.get("users_by_plan", {}).items()
    )

    report = f"""VideoMind Daily Report — {date_str}

USERS: {stats['total_users']} ({plan_breakdown})
JOBS: {stats['total_jobs']} total (Completed: {stats['completed_jobs']}, Failed: {stats['failed_jobs']}, Processing: {stats['processing_jobs']})
SERVER: CPU {cpu:.0f}% | RAM {mem.percent:.0f}% | Disk {disk.percent:.0f}%
ERRORS: {stats['failed_jobs']} failed jobs

---
Status: {"All systems operational" if stats['failed_jobs'] == 0 else "Action needed — check failed jobs"}
"""
    return report
```

**Step 4: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_report.py -v`
Expected: ALL PASS

**Step 5: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

---

### Task 6: Admin Stats Endpoint

**Files:**
- Create: `videomind/app/routers/admin.py`
- Create: `videomind/tests/test_admin.py`
- Modify: `videomind/app/main.py` — add admin router

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_admin.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write admin.py router**

```python
# app/routers/admin.py
from fastapi import APIRouter, Request, HTTPException
from app.config import DATABASE_URL
from app.services.health import check_system_health
from app.services.report import generate_daily_stats

router = APIRouter()


@router.get("/api/v1/admin/stats")
def get_admin_stats(request: Request):
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    health = check_system_health(DATABASE_URL)
    stats = generate_daily_stats(DATABASE_URL)

    return {
        "health": health,
        "stats": stats,
    }
```

**Step 4: Update main.py**

In `videomind/app/main.py`:
- Add `admin` to the routers import line
- Add `app.include_router(admin.router)` after the other router includes

**Step 5: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_admin.py -v`
Expected: ALL PASS

**Step 6: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

---

### Task 7: CLI Scripts for Cron Jobs

**Files:**
- Create: `videomind/scripts/health_check.py`
- Create: `videomind/scripts/cleanup.py`
- Create: `videomind/scripts/daily_report.py`
- Create: `videomind/tests/test_scripts.py`

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_scripts.py -v`
Expected: FAIL — modules don't exist

**Step 3: Create scripts directory and __init__.py**

Create `videomind/scripts/__init__.py` (empty file).

**Step 4: Write health_check.py**

```python
# scripts/health_check.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import DATABASE_URL
from app.services.health import check_system_health, check_stuck_jobs
from app.models import update_job_status
from app.logging_config import setup_logging

logger = setup_logging("health_check_script")


def run_health_check(db_path=None):
    db = db_path or DATABASE_URL
    health = check_system_health(db)

    logger.info(f"Health: {health['status']} | CPU: {health['cpu_percent']:.0f}% | "
                f"RAM: {health['memory_percent']:.0f}% | Disk: {health['disk_percent']:.0f}%")

    if health["stuck_jobs"] > 0:
        logger.warning(f"Found {health['stuck_jobs']} stuck jobs: {health['stuck_job_ids']}")
        for job_id in health["stuck_job_ids"]:
            update_job_status(db, job_id, status="failed", error_message="Timed out — marked by health check")
            logger.info(f"Marked stuck job {job_id} as failed")

    return health


if __name__ == "__main__":
    run_health_check()
```

**Step 5: Write cleanup.py**

```python
# scripts/cleanup.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import TEMP_DIR, FRAMES_DIR
from app.services.cleanup import cleanup_temp_files, cleanup_old_frames
from app.logging_config import setup_logging

logger = setup_logging("cleanup_script")


def run_cleanup(temp_dir=None, frames_dir=None):
    t_dir = temp_dir or TEMP_DIR
    f_dir = frames_dir or FRAMES_DIR

    temp_result = cleanup_temp_files(t_dir, max_age_seconds=3600)
    frames_result = cleanup_old_frames(f_dir, max_age_days=30)

    logger.info(f"Cleanup: {temp_result['deleted']} temp files, "
                f"{frames_result['deleted_dirs']} frame dirs removed")

    return {"temp": temp_result, "frames": frames_result}


if __name__ == "__main__":
    run_cleanup()
```

**Step 6: Write daily_report.py**

```python
# scripts/daily_report.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import DATABASE_URL, ADMIN_EMAIL
from app.services.report import generate_daily_stats, format_daily_report
from app.services.email_utils import send_email
from app.logging_config import setup_logging

logger = setup_logging("daily_report_script")


def run_daily_report(db_path=None):
    db = db_path or DATABASE_URL

    stats = generate_daily_stats(db)
    report = format_daily_report(stats)

    logger.info("Daily report generated:")
    logger.info(report)

    email_result = send_email(
        to_email=ADMIN_EMAIL,
        subject=f"VideoMind Daily Report",
        body=report
    )
    logger.info(f"Email: {email_result['status']}")

    return {"stats": stats, "report": report, "email": email_result}


if __name__ == "__main__":
    run_daily_report()
```

**Step 7: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_scripts.py -v`
Expected: ALL PASS

**Step 8: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

---

### Task 8: Phase 4 End-to-End Test

**Files:**
- Create: `videomind/tests/test_e2e_phase4.py`

**Step 1: Write e2e test**

```python
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
```

**Step 2: Run e2e test**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_e2e_phase4.py -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

---

### Phase 4 Complete Checklist

After all tasks are done, verify:

- [ ] `python -m pytest tests/ -v` — all tests pass (Phase 1 + 2 + 3 + 4)
- [ ] Structured logging configured and used across new services
- [ ] `GET /api/v1/admin/stats` — returns health + stats
- [ ] Health check detects stuck jobs and system resource warnings
- [ ] Cleanup removes old temp files (>1hr) and old frames (>30 days)
- [ ] SendGrid email wrapper works (mocked) with graceful no-API-key handling
- [ ] Daily report generates formatted stats from DB
- [ ] CLI scripts (`scripts/*.py`) are cron-ready entry points
- [ ] All existing Phase 1 + 2 + 3 tests still pass
