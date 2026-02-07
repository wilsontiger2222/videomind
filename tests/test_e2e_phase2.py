# tests/test_e2e_phase2.py
import os
import time
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

TEST_DB = "./data/test_e2e_phase2.db"
AUTH_HEADER = {"Authorization": "Bearer test-key-123"}

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


@patch("app.workers.pipeline.analyze_frames")
@patch("app.workers.pipeline.deduplicate_frames")
@patch("app.workers.pipeline.extract_frames")
@patch("app.workers.pipeline.summarize_transcript")
@patch("app.workers.pipeline.transcribe_audio")
@patch("app.workers.pipeline.extract_audio")
@patch("app.workers.pipeline.download_video")
@patch("app.routers.analyze.DATABASE_URL", TEST_DB)
@patch("app.routers.results.DATABASE_URL", TEST_DB)
@patch("app.routers.ask.DATABASE_URL", TEST_DB)
@patch("app.routers.blog.DATABASE_URL", TEST_DB)
def test_full_phase2_flow(
    mock_download, mock_audio, mock_transcribe, mock_summarize,
    mock_extract_frames, mock_dedup, mock_analyze_frames
):
    # Setup mocks
    mock_download.return_value = {
        "title": "Docker Tutorial", "duration": 600,
        "source": "youtube", "file_path": "/tmp/docker.mp4"
    }
    mock_audio.return_value = "/tmp/docker.wav"
    mock_transcribe.return_value = {
        "full_text": "Welcome to this Docker tutorial. Today we will learn about containers and images.",
        "segments": [
            {"start": 0.0, "end": 5.0, "text": "Welcome to this Docker tutorial."},
            {"start": 5.0, "end": 12.0, "text": "Today we will learn about containers and images."}
        ]
    }
    mock_summarize.return_value = {
        "short": "A beginner Docker tutorial.",
        "detailed": "This tutorial covers Docker containers and images for beginners.",
        "chapters": [{"start": "0:00", "end": "5:00", "title": "Introduction"}, {"start": "5:00", "end": "10:00", "title": "Containers"}]
    }
    mock_extract_frames.return_value = ["/tmp/frames/frame_0001.jpg", "/tmp/frames/frame_0002.jpg", "/tmp/frames/frame_0003.jpg"]
    mock_dedup.return_value = ["/tmp/frames/frame_0001.jpg", "/tmp/frames/frame_0003.jpg"]
    mock_analyze_frames.return_value = [
        {"timestamp": 0.0, "frame_path": "/tmp/frames/frame_0001.jpg", "description": "Title slide: Docker Tutorial"},
        {"timestamp": 10.0, "frame_path": "/tmp/frames/frame_0003.jpg", "description": "Terminal showing docker run command"}
    ]

    # Step 1: Submit video with visual_analysis enabled
    response = client.post(
        "/api/v1/analyze",
        json={"url": "https://youtube.com/watch?v=docker", "options": {"visual_analysis": True}},
        headers=AUTH_HEADER
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    # Step 2: Wait for background processing
    time.sleep(1)

    # Step 3: Get result — should include visual_analysis
    response = client.get(f"/api/v1/result/{job_id}", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["video"]["title"] == "Docker Tutorial"
    assert len(data["visual_analysis"]) == 2
    assert "Title slide" in data["visual_analysis"][0]["description"]

    # Step 4: Ask a question
    with patch("app.routers.ask.answer_question") as mock_qa:
        mock_qa.return_value = {
            "answer": "The docker run command was shown at 0:10.",
            "relevant_timestamps": ["0:10"],
            "relevant_frames": ["/tmp/frames/frame_0003.jpg"]
        }
        response = client.post(
            "/api/v1/ask",
            json={"job_id": job_id, "question": "What Docker command was shown?"},
            headers=AUTH_HEADER
        )
    assert response.status_code == 200
    assert "docker run" in response.json()["answer"]

    # Step 5: Generate blog
    with patch("app.routers.blog.generate_blog") as mock_blog:
        mock_blog.return_value = {
            "title": "Docker Tutorial: Getting Started with Containers",
            "content_markdown": "# Docker Tutorial\n\n## Introduction\n\nLearn Docker basics.",
            "image_suggestions": [{"timestamp": 10.0, "caption": "Docker run command", "insert_after": "## Commands"}]
        }
        response = client.post(
            "/api/v1/to-blog",
            json={"job_id": job_id, "style": "tutorial", "include_images": True},
            headers=AUTH_HEADER
        )
    assert response.status_code == 200
    blog = response.json()
    assert "Docker" in blog["title"]
    assert "# Docker Tutorial" in blog["content_markdown"]
