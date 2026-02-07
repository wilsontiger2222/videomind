# tests/test_usage.py
import os
import pytest
from app.database import init_db
from app.models import (
    create_user, create_job, get_user_usage,
    increment_user_video_count, reset_daily_video_count
)

TEST_DB = "./data/test_usage.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_get_user_usage_new_user():
    result = create_user(TEST_DB, email="usage@example.com", password="securepass123")
    usage = get_user_usage(TEST_DB, result["api_key"])
    assert usage["plan"] == "free"
    assert usage["videos_today"] == 0
    assert usage["videos_limit"] == 3
    assert usage["requests_limit"] == 10


def test_increment_video_count():
    result = create_user(TEST_DB, email="inc@example.com", password="securepass123")
    increment_user_video_count(TEST_DB, result["api_key"])
    increment_user_video_count(TEST_DB, result["api_key"])
    usage = get_user_usage(TEST_DB, result["api_key"])
    assert usage["videos_today"] == 2


def test_reset_daily_video_count():
    result = create_user(TEST_DB, email="reset@example.com", password="securepass123")
    increment_user_video_count(TEST_DB, result["api_key"])
    reset_daily_video_count(TEST_DB, result["api_key"])
    usage = get_user_usage(TEST_DB, result["api_key"])
    assert usage["videos_today"] == 0


def test_usage_limits_by_plan():
    result = create_user(TEST_DB, email="pro@example.com", password="securepass123")
    from app.models import update_user_plan
    update_user_plan(TEST_DB, result["api_key"], plan="pro")
    usage = get_user_usage(TEST_DB, result["api_key"])
    assert usage["videos_limit"] == 30
    assert usage["requests_limit"] == 100


def test_usage_limits_business():
    result = create_user(TEST_DB, email="biz@example.com", password="securepass123")
    from app.models import update_user_plan
    update_user_plan(TEST_DB, result["api_key"], plan="business")
    usage = get_user_usage(TEST_DB, result["api_key"])
    assert usage["videos_limit"] == 150
    assert usage["requests_limit"] == 500
