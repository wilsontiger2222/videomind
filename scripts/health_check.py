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
