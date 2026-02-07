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
        subject="VideoMind Daily Report",
        body=report
    )
    logger.info(f"Email: {email_result['status']}")

    return {"stats": stats, "report": report, "email": email_result}


if __name__ == "__main__":
    run_daily_report()
