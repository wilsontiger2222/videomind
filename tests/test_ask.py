# tests/test_ask.py
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.models import create_job, update_job_status

TEST_DB = "./data/test_ask.db"
AUTH_HEADER = {"Authorization": "Bearer test-key-123"}

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


def test_ask_returns_answer():
    job_id = create_job(TEST_DB, url="https://youtube.com/watch?v=test", options={})
    update_job_status(
        TEST_DB, job_id,
        status="completed",
        transcript_text="At 5:02 he ran docker pull nginx",
        visual_analysis='[{"timestamp": 5.0, "description": "Terminal with docker command"}]',
        chapters='[{"start": "0:00", "end": "10:00", "title": "Docker Setup"}]'
    )

    with patch("app.routers.ask.DATABASE_URL", TEST_DB):
        with patch("app.routers.ask.answer_question") as mock_qa:
            mock_qa.return_value = {
                "answer": "He ran docker pull nginx.",
                "relevant_timestamps": ["5:02"],
                "relevant_frames": []
            }
            response = client.post(
                "/api/v1/ask",
                json={"job_id": job_id, "question": "What command was run?"},
                headers=AUTH_HEADER
            )

    assert response.status_code == 200
    data = response.json()
    assert "docker pull nginx" in data["answer"]


def test_ask_job_not_found():
    with patch("app.routers.ask.DATABASE_URL", TEST_DB):
        response = client.post(
            "/api/v1/ask",
            json={"job_id": "nonexistent", "question": "What?"},
            headers=AUTH_HEADER
        )
    assert response.status_code == 404


def test_ask_job_not_completed():
    job_id = create_job(TEST_DB, url="https://youtube.com/watch?v=test", options={})
    update_job_status(TEST_DB, job_id, status="processing")

    with patch("app.routers.ask.DATABASE_URL", TEST_DB):
        response = client.post(
            "/api/v1/ask",
            json={"job_id": job_id, "question": "What?"},
            headers=AUTH_HEADER
        )
    assert response.status_code == 400
