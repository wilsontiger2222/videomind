import os
import pytest
from unittest.mock import patch, MagicMock
from app.database import init_db
from app.models import create_job, get_job
from app.workers.pipeline import process_video, generate_srt

TEST_DB = "./data/test_pipeline.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

@patch("app.workers.pipeline.summarize_transcript")
@patch("app.workers.pipeline.transcribe_audio")
@patch("app.workers.pipeline.extract_audio")
@patch("app.workers.pipeline.download_video")
@patch("app.workers.pipeline._cleanup_temp")
def test_pipeline_processes_video_successfully(mock_cleanup, mock_download, mock_audio, mock_transcribe, mock_summarize):
    mock_download.return_value = {
        "title": "Test Video",
        "duration": 120,
        "source": "youtube",
        "file_path": "/tmp/test.mp4"
    }
    mock_audio.return_value = "/tmp/test.wav"
    mock_transcribe.return_value = {
        "full_text": "Hello world",
        "segments": [{"start": 0.0, "end": 5.0, "text": "Hello world"}]
    }
    mock_summarize.return_value = {
        "short": "A greeting.",
        "detailed": "The video contains a greeting.",
        "chapters": [{"start": "0:00", "end": "0:05", "title": "Greeting"}]
    }

    job_id = create_job(TEST_DB, url="https://youtube.com/watch?v=test", options={})
    process_video(job_id, TEST_DB)

    job = get_job(TEST_DB, job_id)
    assert job["status"] == "completed"
    assert job["transcript_text"] == "Hello world"
    assert job["summary_short"] == "A greeting."
    assert job["video_title"] == "Test Video"

@patch("app.workers.pipeline.download_video")
@patch("app.workers.pipeline._cleanup_temp")
def test_pipeline_handles_download_failure(mock_cleanup, mock_download):
    mock_download.side_effect = Exception("Download failed")

    job_id = create_job(TEST_DB, url="https://invalid.com", options={})
    process_video(job_id, TEST_DB)

    job = get_job(TEST_DB, job_id)
    assert job["status"] == "failed"
    assert "Download failed" in job["error_message"]

def test_generate_srt():
    segments = [
        {"start": 0.0, "end": 5.2, "text": "Hello world"},
        {"start": 5.2, "end": 10.0, "text": "This is a test"}
    ]
    srt = generate_srt(segments)
    assert "1" in srt
    assert "00:00:00,000 --> 00:00:05,200" in srt
    assert "Hello world" in srt
    assert "2" in srt
