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
