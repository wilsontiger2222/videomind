# VideoMind API — Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a working MVP API that accepts a video URL, transcribes it, generates a summary, and returns results — all running on a single server.

**Architecture:** FastAPI web server with background processing via threading. SQLite database tracks jobs. OpenAI APIs handle transcription (Whisper) and summarization (GPT-4o). yt-dlp downloads videos, FFmpeg extracts audio.

**Tech Stack:** Python 3.14, FastAPI, SQLite, yt-dlp, FFmpeg, OpenAI API (Whisper + GPT-4o)

**Simplifications for MVP:** No Celery/Redis (use BackgroundTasks + threading instead). No Stripe. Hardcoded API keys. No rate limiting. Audio-only (vision comes in Phase 2).

---

### Task 1: Project Scaffolding

**Files:**
- Create: `videomind/requirements.txt`
- Create: `videomind/.env.example`
- Create: `videomind/app/__init__.py`
- Create: `videomind/app/config.py`
- Create: `videomind/tests/__init__.py`

**Step 1: Create project directory structure**

```
videomind/
├── app/
│   ├── __init__.py
│   ├── routers/
│   │   └── __init__.py
│   ├── services/
│   │   └── __init__.py
│   ├── workers/
│   │   └── __init__.py
│   └── middleware/
│       └── __init__.py
├── tests/
│   └── __init__.py
├── data/
│   └── frames/
├── scripts/
├── requirements.txt
└── .env.example
```

**Step 2: Write requirements.txt**

```
fastapi==0.115.0
uvicorn==0.30.0
python-dotenv==1.0.1
openai==1.50.0
yt-dlp==2024.10.22
aiosqlite==0.20.0
httpx==0.27.0
pytest==8.3.0
pytest-asyncio==0.24.0
```

**Step 3: Write .env.example**

```
OPENAI_API_KEY=sk-your-key-here
API_KEYS=test-key-123,test-key-456
DATA_DIR=./data
```

**Step 4: Write config.py**

```python
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
API_KEYS = os.getenv("API_KEYS", "test-key-123").split(",")
DATA_DIR = os.getenv("DATA_DIR", "./data")
DATABASE_URL = os.path.join(DATA_DIR, "videomind.db")
FRAMES_DIR = os.path.join(DATA_DIR, "frames")
TEMP_DIR = os.path.join(DATA_DIR, "temp")
```

**Step 5: Install dependencies**

Run: `cd videomind && python -m pip install -r requirements.txt`

**Step 6: Create .env from example**

Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY`.

**Step 7: Initialize git**

```bash
cd videomind
git init
echo "__pycache__/\n*.pyc\n.env\ndata/\n*.db" > .gitignore
git add .
git commit -m "feat: project scaffolding"
```

---

### Task 2: Database Layer

**Files:**
- Create: `videomind/app/database.py`
- Create: `videomind/app/models.py`
- Create: `videomind/tests/test_database.py`

**Step 1: Write the failing test**

```python
# tests/test_database.py
import os
import pytest
from app.database import init_db, get_db
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
```

**Step 2: Run test to verify it fails**

Run: `cd videomind && python -m pytest tests/test_database.py -v`
Expected: FAIL — modules don't exist yet

**Step 3: Write database.py**

```python
# app/database.py
import sqlite3
import os
from app.config import DATABASE_URL

def get_connection(db_path=None):
    path = db_path or DATABASE_URL
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path=None):
    path = db_path or DATABASE_URL
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = get_connection(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            options TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            step TEXT DEFAULT '',
            video_title TEXT DEFAULT '',
            video_duration TEXT DEFAULT '',
            video_source TEXT DEFAULT '',
            transcript_text TEXT DEFAULT '',
            transcript_segments TEXT DEFAULT '[]',
            summary_short TEXT DEFAULT '',
            summary_detailed TEXT DEFAULT '',
            chapters TEXT DEFAULT '[]',
            subtitles_srt TEXT DEFAULT '',
            error_message TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
```

**Step 4: Write models.py**

```python
# app/models.py
import uuid
import json
from app.database import get_connection

def create_job(db_path, url, options):
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO jobs (id, url, options) VALUES (?, ?, ?)",
        (job_id, url, json.dumps(options))
    )
    conn.commit()
    conn.close()
    return job_id

def get_job(db_path, job_id):
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)

def update_job_status(db_path, job_id, status=None, progress=None, step=None, **kwargs):
    conn = get_connection(db_path)
    updates = []
    values = []
    if status is not None:
        updates.append("status = ?")
        values.append(status)
    if progress is not None:
        updates.append("progress = ?")
        values.append(progress)
    if step is not None:
        updates.append("step = ?")
        values.append(step)
    for key, value in kwargs.items():
        updates.append(f"{key} = ?")
        values.append(value if isinstance(value, str) else json.dumps(value))
    if status == "completed" or status == "failed":
        updates.append("completed_at = CURRENT_TIMESTAMP")
    values.append(job_id)
    conn.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?", values)
    conn.commit()
    conn.close()
```

**Step 5: Run test to verify it passes**

Run: `cd videomind && python -m pytest tests/test_database.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add app/database.py app/models.py tests/test_database.py
git commit -m "feat: database layer with job CRUD"
```

---

### Task 3: FastAPI App Skeleton

**Files:**
- Create: `videomind/app/main.py`
- Create: `videomind/tests/test_main.py`

**Step 1: Write the failing test**

```python
# tests/test_main.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
```

**Step 2: Run test to verify it fails**

Run: `cd videomind && python -m pytest tests/test_main.py -v`
Expected: FAIL — app doesn't exist yet

**Step 3: Write main.py**

```python
# app/main.py
from fastapi import FastAPI
from app.database import init_db

app = FastAPI(
    title="VideoMind API",
    description="Turn any video into text, summaries, and insights",
    version="0.1.0"
)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "VideoMind API"
    }
```

**Step 4: Run test to verify it passes**

Run: `cd videomind && python -m pytest tests/test_main.py -v`
Expected: PASS

**Step 5: Verify server starts**

Run: `cd videomind && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
Visit: `http://localhost:8000/api/v1/health`
Expected: `{"status":"healthy","version":"0.1.0","service":"VideoMind API"}`
Stop server with Ctrl+C.

**Step 6: Commit**

```bash
git add app/main.py tests/test_main.py
git commit -m "feat: FastAPI skeleton with health endpoint"
```

---

### Task 4: Video Downloader Service

**Files:**
- Create: `videomind/app/services/downloader.py`
- Create: `videomind/tests/test_downloader.py`

**Step 1: Write the failing test**

```python
# tests/test_downloader.py
import os
import pytest
from unittest.mock import patch, MagicMock
from app.services.downloader import download_video

@patch("app.services.downloader.yt_dlp.YoutubeDL")
def test_download_video_returns_metadata(mock_ytdl_class):
    mock_ytdl = MagicMock()
    mock_ytdl_class.return_value.__enter__ = MagicMock(return_value=mock_ytdl)
    mock_ytdl_class.return_value.__exit__ = MagicMock(return_value=False)
    mock_ytdl.extract_info.return_value = {
        "title": "Test Video",
        "duration": 120,
        "webpage_url": "https://youtube.com/watch?v=test",
        "extractor": "youtube",
    }
    mock_ytdl.prepare_filename.return_value = "/tmp/test_video.mp4"

    result = download_video("https://youtube.com/watch?v=test", output_dir="/tmp")

    assert result["title"] == "Test Video"
    assert result["duration"] == 120
    assert result["file_path"] == "/tmp/test_video.mp4"

@patch("app.services.downloader.yt_dlp.YoutubeDL")
def test_download_video_invalid_url(mock_ytdl_class):
    mock_ytdl = MagicMock()
    mock_ytdl_class.return_value.__enter__ = MagicMock(return_value=mock_ytdl)
    mock_ytdl_class.return_value.__exit__ = MagicMock(return_value=False)
    mock_ytdl.extract_info.side_effect = Exception("Unsupported URL")

    with pytest.raises(Exception, match="Unsupported URL"):
        download_video("https://invalid-url.com", output_dir="/tmp")
```

**Step 2: Run test to verify it fails**

Run: `cd videomind && python -m pytest tests/test_downloader.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write downloader.py**

```python
# app/services/downloader.py
import os
import yt_dlp

def download_video(url: str, output_dir: str) -> dict:
    os.makedirs(output_dir, exist_ok=True)

    ydl_opts = {
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
        "format": "best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)

    return {
        "title": info.get("title", "Unknown"),
        "duration": info.get("duration", 0),
        "source": info.get("extractor", "unknown"),
        "file_path": file_path,
    }
```

**Step 4: Run test to verify it passes**

Run: `cd videomind && python -m pytest tests/test_downloader.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/downloader.py tests/test_downloader.py
git commit -m "feat: video download service with yt-dlp"
```

---

### Task 5: Audio Extraction Service

**Files:**
- Create: `videomind/app/services/audio.py`
- Create: `videomind/tests/test_audio.py`

**Step 1: Write the failing test**

```python
# tests/test_audio.py
import pytest
from unittest.mock import patch
from app.services.audio import extract_audio

@patch("app.services.audio.subprocess.run")
def test_extract_audio_creates_wav(mock_run):
    mock_run.return_value = None

    result = extract_audio("/tmp/video.mp4", "/tmp")

    assert result == "/tmp/video.wav"
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "ffmpeg" in call_args[0]
    assert "/tmp/video.mp4" in call_args

@patch("app.services.audio.subprocess.run")
def test_extract_audio_ffmpeg_fails(mock_run):
    mock_run.side_effect = Exception("FFmpeg not found")

    with pytest.raises(Exception, match="FFmpeg not found"):
        extract_audio("/tmp/video.mp4", "/tmp")
```

**Step 2: Run test to verify it fails**

Run: `cd videomind && python -m pytest tests/test_audio.py -v`
Expected: FAIL

**Step 3: Write audio.py**

```python
# app/services/audio.py
import os
import subprocess

def extract_audio(video_path: str, output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    audio_path = os.path.join(output_dir, f"{base_name}.wav")

    subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-vn",                    # no video
            "-acodec", "pcm_s16le",   # wav format
            "-ar", "16000",           # 16kHz sample rate (optimal for Whisper)
            "-ac", "1",               # mono
            "-y",                     # overwrite
            audio_path
        ],
        check=True,
        capture_output=True
    )

    return audio_path
```

**Step 4: Run test to verify it passes**

Run: `cd videomind && python -m pytest tests/test_audio.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/audio.py tests/test_audio.py
git commit -m "feat: audio extraction service with FFmpeg"
```

---

### Task 6: Transcription Service

**Files:**
- Create: `videomind/app/services/transcriber.py`
- Create: `videomind/tests/test_transcriber.py`

**Step 1: Write the failing test**

```python
# tests/test_transcriber.py
import pytest
from unittest.mock import patch, MagicMock, mock_open
from app.services.transcriber import transcribe_audio

@patch("builtins.open", mock_open(read_data=b"fake audio data"))
@patch("app.services.transcriber.openai.OpenAI")
def test_transcribe_returns_segments(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_segment_1 = MagicMock()
    mock_segment_1.start = 0.0
    mock_segment_1.end = 5.0
    mock_segment_1.text = "Hello world"

    mock_segment_2 = MagicMock()
    mock_segment_2.start = 5.0
    mock_segment_2.end = 10.0
    mock_segment_2.text = "This is a test"

    mock_response = MagicMock()
    mock_response.text = "Hello world This is a test"
    mock_response.segments = [mock_segment_1, mock_segment_2]

    mock_client.audio.transcriptions.create.return_value = mock_response

    result = transcribe_audio("/tmp/audio.wav")

    assert result["full_text"] == "Hello world This is a test"
    assert len(result["segments"]) == 2
    assert result["segments"][0]["text"] == "Hello world"
    assert result["segments"][0]["start"] == 0.0
```

**Step 2: Run test to verify it fails**

Run: `cd videomind && python -m pytest tests/test_transcriber.py -v`
Expected: FAIL

**Step 3: Write transcriber.py**

```python
# app/services/transcriber.py
import openai
from app.config import OPENAI_API_KEY

def transcribe_audio(audio_path: str) -> dict:
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    with open(audio_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )

    segments = []
    if hasattr(response, "segments") and response.segments:
        for seg in response.segments:
            segments.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip()
            })

    return {
        "full_text": response.text.strip(),
        "segments": segments
    }
```

**Step 4: Run test to verify it passes**

Run: `cd videomind && python -m pytest tests/test_transcriber.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/transcriber.py tests/test_transcriber.py
git commit -m "feat: transcription service via OpenAI Whisper API"
```

---

### Task 7: Summary Service

**Files:**
- Create: `videomind/app/services/summarizer.py`
- Create: `videomind/tests/test_summarizer.py`

**Step 1: Write the failing test**

```python
# tests/test_summarizer.py
import pytest
from unittest.mock import patch, MagicMock
from app.services.summarizer import summarize_transcript

@patch("app.services.summarizer.openai.OpenAI")
def test_summarize_returns_short_and_detailed(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = '{"short": "A tutorial about Docker.", "detailed": "This video covers Docker installation, basic commands, and deployment.", "chapters": [{"start": "0:00", "end": "5:00", "title": "Introduction"}]}'

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_response

    result = summarize_transcript("This is a transcript about Docker...")

    assert result["short"] == "A tutorial about Docker."
    assert "Docker" in result["detailed"]
    assert len(result["chapters"]) == 1
```

**Step 2: Run test to verify it fails**

Run: `cd videomind && python -m pytest tests/test_summarizer.py -v`
Expected: FAIL

**Step 3: Write summarizer.py**

```python
# app/services/summarizer.py
import json
import openai
from app.config import OPENAI_API_KEY

def summarize_transcript(transcript: str) -> dict:
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You analyze video transcripts. Return a JSON object with exactly these keys:\n"
                    '- "short": A 1-2 sentence summary\n'
                    '- "detailed": A 3-5 sentence detailed summary\n'
                    '- "chapters": An array of objects with "start", "end", "title" '
                    "representing logical sections of the video.\n"
                    "Estimate timestamps based on the transcript flow. "
                    "Return ONLY valid JSON, no markdown."
                )
            },
            {
                "role": "user",
                "content": f"Summarize this video transcript:\n\n{transcript[:8000]}"
            }
        ],
        temperature=0.3,
        max_tokens=1500
    )

    raw = response.choices[0].message.content.strip()
    # Handle potential markdown code blocks in response
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    data = json.loads(raw)

    return {
        "short": data.get("short", ""),
        "detailed": data.get("detailed", ""),
        "chapters": data.get("chapters", [])
    }
```

**Step 4: Run test to verify it passes**

Run: `cd videomind && python -m pytest tests/test_summarizer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/summarizer.py tests/test_summarizer.py
git commit -m "feat: summary and chapter generation via GPT-4o"
```

---

### Task 8: Processing Pipeline

**Files:**
- Create: `videomind/app/workers/pipeline.py`
- Create: `videomind/tests/test_pipeline.py`

**Step 1: Write the failing test**

```python
# tests/test_pipeline.py
import os
import pytest
from unittest.mock import patch, MagicMock
from app.database import init_db
from app.models import create_job, get_job
from app.workers.pipeline import process_video

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
def test_pipeline_processes_video_successfully(mock_download, mock_audio, mock_transcribe, mock_summarize):
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
def test_pipeline_handles_download_failure(mock_download):
    mock_download.side_effect = Exception("Download failed")

    job_id = create_job(TEST_DB, url="https://invalid.com", options={})
    process_video(job_id, TEST_DB)

    job = get_job(TEST_DB, job_id)
    assert job["status"] == "failed"
    assert "Download failed" in job["error_message"]
```

**Step 2: Run test to verify it fails**

Run: `cd videomind && python -m pytest tests/test_pipeline.py -v`
Expected: FAIL

**Step 3: Write pipeline.py**

```python
# app/workers/pipeline.py
import os
import json
from app.models import get_job, update_job_status
from app.services.downloader import download_video
from app.services.audio import extract_audio
from app.services.transcriber import transcribe_audio
from app.services.summarizer import summarize_transcript
from app.config import TEMP_DIR

def process_video(job_id: str, db_path: str = None):
    from app.config import DATABASE_URL
    db = db_path or DATABASE_URL

    try:
        job = get_job(db, job_id)
        if job is None:
            return

        temp_dir = os.path.join(TEMP_DIR, job_id)
        os.makedirs(temp_dir, exist_ok=True)

        # Step 1: Download video
        update_job_status(db, job_id, status="processing", progress=10, step="Downloading video...")
        video_info = download_video(job["url"], temp_dir)

        update_job_status(
            db, job_id, progress=25, step="Extracting audio...",
            video_title=video_info["title"],
            video_duration=str(video_info["duration"]),
            video_source=video_info["source"]
        )

        # Step 2: Extract audio
        audio_path = extract_audio(video_info["file_path"], temp_dir)
        update_job_status(db, job_id, progress=40, step="Transcribing audio...")

        # Step 3: Transcribe
        transcript = transcribe_audio(audio_path)
        update_job_status(
            db, job_id, progress=70, step="Generating summary...",
            transcript_text=transcript["full_text"],
            transcript_segments=json.dumps(transcript["segments"])
        )

        # Step 4: Summarize
        summary = summarize_transcript(transcript["full_text"])

        # Step 5: Generate SRT subtitles
        srt = generate_srt(transcript["segments"])

        # Step 6: Mark complete
        update_job_status(
            db, job_id,
            status="completed",
            progress=100,
            step="Done",
            summary_short=summary["short"],
            summary_detailed=summary["detailed"],
            chapters=json.dumps(summary["chapters"]),
            subtitles_srt=srt
        )

    except Exception as e:
        update_job_status(
            db, job_id,
            status="failed",
            step="Error",
            error_message=str(e)
        )

    finally:
        # Clean up temp files
        _cleanup_temp(temp_dir)


def generate_srt(segments: list) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        start = _seconds_to_srt(seg["start"])
        end = _seconds_to_srt(seg["end"])
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


def _seconds_to_srt(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _cleanup_temp(temp_dir: str):
    try:
        if os.path.exists(temp_dir):
            for f in os.listdir(temp_dir):
                try:
                    os.remove(os.path.join(temp_dir, f))
                except OSError:
                    pass
            os.rmdir(temp_dir)
    except OSError:
        pass
```

**Step 4: Run test to verify it passes**

Run: `cd videomind && python -m pytest tests/test_pipeline.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/workers/pipeline.py tests/test_pipeline.py
git commit -m "feat: video processing pipeline with download/transcribe/summarize"
```

---

### Task 9: API Endpoints (Analyze, Status, Result)

**Files:**
- Create: `videomind/app/routers/analyze.py`
- Create: `videomind/app/routers/results.py`
- Modify: `videomind/app/main.py` — add router imports
- Create: `videomind/tests/test_endpoints.py`

**Step 1: Write the failing test**

```python
# tests/test_endpoints.py
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.models import create_job, update_job_status

TEST_DB = "./data/test_endpoints.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    with patch("app.config.DATABASE_URL", TEST_DB):
        with patch("app.routers.analyze.DATABASE_URL", TEST_DB):
            with patch("app.routers.results.DATABASE_URL", TEST_DB):
                yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)

def test_analyze_returns_job_id():
    with patch("app.routers.analyze.DATABASE_URL", TEST_DB):
        with patch("app.routers.analyze.BackgroundTasks.add_task"):
            response = client.post(
                "/api/v1/analyze",
                json={"url": "https://youtube.com/watch?v=test"},
                headers={"Authorization": "Bearer test-key-123"}
            )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "processing"

def test_analyze_missing_url():
    response = client.post(
        "/api/v1/analyze",
        json={},
        headers={"Authorization": "Bearer test-key-123"}
    )
    assert response.status_code == 422

def test_status_endpoint():
    job_id = create_job(TEST_DB, url="https://youtube.com/watch?v=test", options={})
    update_job_status(TEST_DB, job_id, status="processing", progress=50, step="Transcribing...")

    with patch("app.routers.results.DATABASE_URL", TEST_DB):
        response = client.get(
            f"/api/v1/status/{job_id}",
            headers={"Authorization": "Bearer test-key-123"}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"
    assert data["progress"] == 50

def test_result_not_found():
    with patch("app.routers.results.DATABASE_URL", TEST_DB):
        response = client.get(
            "/api/v1/result/nonexistent",
            headers={"Authorization": "Bearer test-key-123"}
        )
    assert response.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `cd videomind && python -m pytest tests/test_endpoints.py -v`
Expected: FAIL

**Step 3: Write analyze.py router**

```python
# app/routers/analyze.py
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional
from app.models import create_job
from app.workers.pipeline import process_video
from app.config import DATABASE_URL

router = APIRouter()

class AnalyzeRequest(BaseModel):
    url: str
    options: Optional[dict] = None

@router.post("/api/v1/analyze")
def analyze_video(request: AnalyzeRequest, background_tasks: BackgroundTasks):
    if not request.url:
        raise HTTPException(status_code=400, detail="URL is required")

    options = request.options or {
        "transcript": True,
        "summary": True,
        "chapters": True,
        "subtitles": True,
    }

    job_id = create_job(DATABASE_URL, url=request.url, options=options)
    background_tasks.add_task(process_video, job_id, DATABASE_URL)

    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Video submitted for processing"
    }
```

**Step 4: Write results.py router**

```python
# app/routers/results.py
import json
from fastapi import APIRouter, HTTPException
from app.models import get_job
from app.config import DATABASE_URL

router = APIRouter()

@router.get("/api/v1/status/{job_id}")
def get_status(job_id: str):
    job = get_job(DATABASE_URL, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job["id"],
        "status": job["status"],
        "progress": job["progress"],
        "step": job["step"]
    }

@router.get("/api/v1/result/{job_id}")
def get_result(job_id: str):
    job = get_job(DATABASE_URL, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] == "processing":
        return {
            "job_id": job["id"],
            "status": "processing",
            "progress": job["progress"],
            "step": job["step"],
            "message": "Video is still being processed"
        }

    if job["status"] == "failed":
        return {
            "job_id": job["id"],
            "status": "failed",
            "error": job["error_message"]
        }

    return {
        "job_id": job["id"],
        "status": "completed",
        "video": {
            "title": job["video_title"],
            "duration": job["video_duration"],
            "source": job["video_source"]
        },
        "transcript": {
            "full_text": job["transcript_text"],
            "segments": json.loads(job["transcript_segments"] or "[]")
        },
        "summary": {
            "short": job["summary_short"],
            "detailed": job["summary_detailed"]
        },
        "chapters": json.loads(job["chapters"] or "[]"),
        "subtitles_srt": job["subtitles_srt"]
    }
```

**Step 5: Update main.py to include routers**

```python
# app/main.py
from fastapi import FastAPI
from app.database import init_db
from app.routers import analyze, results

app = FastAPI(
    title="VideoMind API",
    description="Turn any video into text, summaries, and insights",
    version="0.1.0"
)

app.include_router(analyze.router)
app.include_router(results.router)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "VideoMind API"
    }
```

**Step 6: Run tests to verify they pass**

Run: `cd videomind && python -m pytest tests/test_endpoints.py -v`
Expected: PASS

**Step 7: Run ALL tests**

Run: `cd videomind && python -m pytest tests/ -v`
Expected: ALL PASS

**Step 8: Commit**

```bash
git add app/routers/ app/main.py tests/test_endpoints.py
git commit -m "feat: analyze, status, and result API endpoints"
```

---

### Task 10: API Key Authentication Middleware

**Files:**
- Create: `videomind/app/middleware/auth.py`
- Modify: `videomind/app/main.py` — add auth middleware
- Create: `videomind/tests/test_auth.py`

**Step 1: Write the failing test**

```python
# tests/test_auth.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_request_without_api_key_is_rejected():
    response = client.post("/api/v1/analyze", json={"url": "https://youtube.com/watch?v=test"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing API key"

def test_request_with_invalid_api_key_is_rejected():
    response = client.post(
        "/api/v1/analyze",
        json={"url": "https://youtube.com/watch?v=test"},
        headers={"Authorization": "Bearer invalid-key"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"

def test_request_with_valid_api_key_passes():
    response = client.get(
        "/api/v1/health",
        headers={"Authorization": "Bearer test-key-123"}
    )
    assert response.status_code == 200

def test_health_endpoint_works_without_key():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `cd videomind && python -m pytest tests/test_auth.py -v`
Expected: FAIL (no auth middleware yet, so unauthenticated requests pass)

**Step 3: Write auth middleware**

```python
# app/middleware/auth.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import API_KEYS

# Endpoints that don't require authentication
PUBLIC_PATHS = ["/api/v1/health", "/docs", "/openapi.json", "/redoc"]

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="Missing API key")

        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Invalid API key format")

        api_key = auth_header.replace("Bearer ", "")
        if api_key not in API_KEYS:
            raise HTTPException(status_code=401, detail="Invalid API key")

        return await call_next(request)
```

**Step 4: Update main.py to add middleware**

Add to `app/main.py` after creating the app:

```python
# app/main.py
from fastapi import FastAPI
from app.database import init_db
from app.routers import analyze, results
from app.middleware.auth import APIKeyMiddleware

app = FastAPI(
    title="VideoMind API",
    description="Turn any video into text, summaries, and insights",
    version="0.1.0"
)

app.add_middleware(APIKeyMiddleware)
app.include_router(analyze.router)
app.include_router(results.router)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "VideoMind API"
    }
```

**Step 5: Run auth tests**

Run: `cd videomind && python -m pytest tests/test_auth.py -v`
Expected: PASS

**Step 6: Run ALL tests to make sure nothing broke**

Run: `cd videomind && python -m pytest tests/ -v`
Expected: ALL PASS (some endpoint tests may need auth headers added — fix if needed)

**Step 7: Commit**

```bash
git add app/middleware/auth.py app/main.py tests/test_auth.py
git commit -m "feat: API key authentication middleware"
```

---

### Task 11: End-to-End Smoke Test

**Files:**
- Create: `videomind/tests/test_e2e.py`

**Step 1: Write end-to-end test**

```python
# tests/test_e2e.py
import os
import time
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

TEST_DB = "./data/test_e2e.db"
AUTH_HEADER = {"Authorization": "Bearer test-key-123"}

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
@patch("app.routers.analyze.DATABASE_URL", TEST_DB)
@patch("app.routers.results.DATABASE_URL", TEST_DB)
def test_full_flow(mock_download, mock_audio, mock_transcribe, mock_summarize):
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
        headers=AUTH_HEADER
    )
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    # Step 2: Wait briefly for background task
    time.sleep(1)

    # Step 3: Get result
    with patch("app.routers.results.DATABASE_URL", TEST_DB):
        response = client.get(f"/api/v1/result/{job_id}", headers=AUTH_HEADER)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["video"]["title"] == "Test Video"
    assert "Python" in data["transcript"]["full_text"]
    assert data["summary"]["short"] == "A Python tutorial."
```

**Step 2: Run e2e test**

Run: `cd videomind && python -m pytest tests/test_e2e.py -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `cd videomind && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 4: Final commit**

```bash
git add tests/test_e2e.py
git commit -m "test: end-to-end smoke test for full video processing flow"
```

---

### Phase 1 Complete Checklist

After all tasks are done, verify:

- [ ] `python -m pytest tests/ -v` — all tests pass
- [ ] `python -m uvicorn app.main:app --port 8000` — server starts
- [ ] `GET /api/v1/health` — returns healthy
- [ ] `POST /api/v1/analyze` without auth — returns 401
- [ ] `POST /api/v1/analyze` with auth + URL — returns job_id
- [ ] `GET /api/v1/status/{job_id}` — returns progress
- [ ] `GET /api/v1/result/{job_id}` — returns full results after processing

### What's Next (Phase 2)

Phase 2 adds:
1. Frame extraction with smart deduplication (FFmpeg + image hashing)
2. GPT-4o Vision analysis of key frames
3. Merged audio+visual timeline
4. Q&A endpoint (`POST /api/v1/ask`)
5. Video-to-blog endpoint (`POST /api/v1/to-blog`)
