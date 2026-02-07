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
