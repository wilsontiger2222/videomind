import os
import pytest
from app.database import init_db, get_connection
from app.models import create_job, get_job, update_job_status

TEST_DB = "./data/test_videomind.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

def test_create_and_get_job():
    job_id = create_job(TEST_DB, url="https://youtube.com/watch?v=test", options={"transcript": True})
    assert job_id is not None
    job = get_job(TEST_DB, job_id)
    assert job["url"] == "https://youtube.com/watch?v=test"
    assert job["status"] == "pending"

def test_update_job_status():
    job_id = create_job(TEST_DB, url="https://youtube.com/watch?v=test", options={})
    update_job_status(TEST_DB, job_id, status="processing", progress=50, step="Transcribing...")
    job = get_job(TEST_DB, job_id)
    assert job["status"] == "processing"
    assert job["progress"] == 50
    assert job["step"] == "Transcribing..."

def test_job_stores_visual_analysis():
    job_id = create_job(TEST_DB, url="https://youtube.com/watch?v=test", options={})
    update_job_status(
        TEST_DB, job_id,
        visual_analysis='[{"timestamp": 5.0, "description": "A code editor"}]'
    )
    job = get_job(TEST_DB, job_id)
    assert '"timestamp": 5.0' in job["visual_analysis"]
