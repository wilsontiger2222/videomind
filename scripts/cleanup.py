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
