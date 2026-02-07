import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.database import init_db
from app.models import create_job, update_job_status

TEST_DB = "./data/test_endpoints.db"
AUTH = {"Authorization": "Bearer test-key-123"}

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)

@patch("app.routers.analyze.DATABASE_URL", TEST_DB)
def test_analyze_returns_job_id(client):
    with patch("app.workers.pipeline.process_video"):
        response = client.post(
            "/api/v1/analyze",
            json={"url": "https://youtube.com/watch?v=test"},
            headers=AUTH
        )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "processing"

def test_analyze_missing_url(client):
    response = client.post("/api/v1/analyze", json={}, headers=AUTH)
    assert response.status_code == 422

@patch("app.routers.results.DATABASE_URL", TEST_DB)
def test_status_endpoint(client):
    job_id = create_job(TEST_DB, url="https://youtube.com/watch?v=test", options={})
    update_job_status(TEST_DB, job_id, status="processing", progress=50, step="Transcribing...")

    response = client.get(f"/api/v1/status/{job_id}", headers=AUTH)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"
    assert data["progress"] == 50

@patch("app.routers.results.DATABASE_URL", TEST_DB)
def test_result_not_found(client):
    response = client.get("/api/v1/result/nonexistent", headers=AUTH)
    assert response.status_code == 404

def test_result_includes_visual_analysis(client):
    job_id = create_job(TEST_DB, url="https://youtube.com/watch?v=test", options={})
    update_job_status(
        TEST_DB, job_id,
        status="completed",
        video_title="Test",
        video_duration="60",
        video_source="youtube",
        transcript_text="Hello",
        transcript_segments="[]",
        summary_short="Short",
        summary_detailed="Detailed",
        chapters="[]",
        subtitles_srt="",
        visual_analysis='[{"timestamp": 5.0, "frame_path": "/frames/f1.jpg", "description": "A terminal"}]'
    )

    with patch("app.routers.results.DATABASE_URL", TEST_DB):
        response = client.get(
            f"/api/v1/result/{job_id}",
            headers={"Authorization": "Bearer test-key-123"}
        )
    assert response.status_code == 200
    data = response.json()
    assert "visual_analysis" in data
    assert len(data["visual_analysis"]) == 1
    assert data["visual_analysis"][0]["description"] == "A terminal"
