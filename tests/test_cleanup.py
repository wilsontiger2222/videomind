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
    for d in [TEMP_DIR, FRAMES_DIR]:
        if os.path.exists(d):
            for root, dirs, files in os.walk(d, topdown=False):
                for f in files:
                    os.remove(os.path.join(root, f))
                for dd in dirs:
                    os.rmdir(os.path.join(root, dd))
            if os.path.exists(d):
                os.rmdir(d)


def test_cleanup_temp_files_removes_old_files():
    old_file = os.path.join(TEMP_DIR, "old_video.mp4")
    with open(old_file, "w") as f:
        f.write("old data")
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
