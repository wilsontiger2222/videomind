import os
import time
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.database import init_db
from app.main import app

TEST_DB = "./data/test_e2e.db"
AUTH = {"Authorization": "Bearer test-key-123"}

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)

@patch("app.workers.pipeline.summarize_transcript")
@patch("app.workers.pipeline.transcribe_audio")
@patch("app.workers.pipeline.extract_audio")
@patch("app.workers.pipeline.download_video")
@patch("app.workers.pipeline._cleanup_temp")
@patch("app.routers.analyze.DATABASE_URL", TEST_DB)
@patch("app.routers.results.DATABASE_URL", TEST_DB)
def test_full_flow(mock_cleanup, mock_download, mock_audio, mock_transcribe, mock_summarize):
    mock_download.return_value = {
        "title": "Test Video", "duration": 60,
        "source": "youtube", "file_path": "/tmp/test.mp4"
    }
    mock_audio.return_value = "/tmp/test.wav"
    mock_transcribe.return_value = {
        "full_text": "This is a test video about Python.",
        "segments": [{"start": 0.0, "end": 5.0, "text": "This is a test video about Python."}]
    }
    mock_summarize.return_value = {
        "short": "A Python tutorial.",
        "detailed": "This video teaches Python basics.",
        "chapters": [{"start": "0:00", "end": "1:00", "title": "Intro"}]
    }

    # Step 1: Submit video
    response = client.post(
        "/api/v1/analyze",
        json={"url": "https://youtube.com/watch?v=test"},
        headers=AUTH
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    # Step 2: Wait for background task
    time.sleep(1)

    # Step 3: Get result
    response = client.get(f"/api/v1/result/{job_id}", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["video"]["title"] == "Test Video"
    assert "Python" in data["transcript"]["full_text"]
    assert data["summary"]["short"] == "A Python tutorial."

def test_unauthenticated_analyze_rejected():
    response = client.post("/api/v1/analyze", json={"url": "https://youtube.com/watch?v=test"})
    assert response.status_code == 401

def test_health_no_auth_needed():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
