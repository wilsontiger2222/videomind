# tests/test_blog.py
import os
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.models import create_job, update_job_status

TEST_DB = "./data/test_blog.db"
AUTH_HEADER = {"Authorization": "Bearer test-key-123"}

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


def test_blog_returns_article():
    job_id = create_job(TEST_DB, url="https://youtube.com/watch?v=test", options={})
    update_job_status(
        TEST_DB, job_id,
        status="completed",
        transcript_text="This is a Docker tutorial about containers.",
        summary_short="A Docker tutorial.",
        summary_detailed="Covers Docker basics.",
        visual_analysis='[{"timestamp": 5.0, "description": "Terminal window"}]',
        chapters='[{"start": "0:00", "end": "5:00", "title": "Introduction"}]'
    )

    with patch("app.routers.blog.DATABASE_URL", TEST_DB):
        with patch("app.routers.blog.generate_blog") as mock_blog:
            mock_blog.return_value = {
                "title": "Docker Guide",
                "content_markdown": "# Docker Guide\n\nContent here.",
                "image_suggestions": []
            }
            response = client.post(
                "/api/v1/to-blog",
                json={"job_id": job_id, "style": "tutorial", "include_images": True},
                headers=AUTH_HEADER
            )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Docker Guide"
    assert "# Docker Guide" in data["content_markdown"]


def test_blog_job_not_found():
    with patch("app.routers.blog.DATABASE_URL", TEST_DB):
        response = client.post(
            "/api/v1/to-blog",
            json={"job_id": "nonexistent", "style": "article"},
            headers=AUTH_HEADER
        )
    assert response.status_code == 404


def test_blog_job_not_completed():
    job_id = create_job(TEST_DB, url="https://youtube.com/watch?v=test", options={})
    update_job_status(TEST_DB, job_id, status="processing")

    with patch("app.routers.blog.DATABASE_URL", TEST_DB):
        response = client.post(
            "/api/v1/to-blog",
            json={"job_id": job_id, "style": "article"},
            headers=AUTH_HEADER
        )
    assert response.status_code == 400
