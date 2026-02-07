# app/services/report.py
import psutil
from datetime import datetime
from app.database import get_connection
from app.logging_config import setup_logging

logger = setup_logging("report")


def generate_daily_stats(db_path):
    """Query the database for daily statistics."""
    conn = get_connection(db_path)

    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    plan_rows = conn.execute(
        "SELECT plan, COUNT(*) as count FROM users GROUP BY plan"
    ).fetchall()
    users_by_plan = {row["plan"]: row["count"] for row in plan_rows}

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
