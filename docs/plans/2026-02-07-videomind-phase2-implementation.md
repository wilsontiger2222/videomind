# VideoMind API — Phase 2 Implementation Plan (Vision + Features)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add visual frame analysis (GPT-4o Vision), Q&A over video content, and video-to-blog conversion to the existing MVP API.

**Architecture:** Extends the Phase 1 pipeline with FFmpeg frame extraction, perceptual image hashing for deduplication (skip near-identical frames), GPT-4o Vision for frame descriptions, and two new endpoints (/ask, /to-blog) that use GPT-4o to reason over stored transcript + visual data.

**Tech Stack:** Python 3.14, FastAPI, SQLite, FFmpeg (frame extraction), Pillow + imagehash (frame dedup), OpenAI API (GPT-4o Vision + GPT-4o text)

**Simplifications for Phase 2:** Key frames stored on local filesystem (no S3/CDN). Vision analysis stored as JSON in SQLite. No caching layer for Q&A responses.

---

### Task 1: Add Dependencies for Phase 2

**Files:**
- Modify: `videomind/requirements.txt`

**Step 1: Update requirements.txt**

Add these lines to the end of `videomind/requirements.txt`:

```
Pillow==11.0.0
imagehash==4.3.1
```

**Step 2: Install new dependencies**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pip install Pillow==11.0.0 imagehash==4.3.1`
Expected: Successful install

**Step 3: Verify imports work**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -c "import PIL; import imagehash; print('OK')"`
Expected: `OK`

**Step 4: Run existing tests to confirm nothing broke**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL 23 PASS

**Step 5: Commit**

```bash
git add requirements.txt
git commit -m "chore: add Pillow and imagehash for Phase 2 frame extraction"
```

---

### Task 2: Frame Extraction Service

**Files:**
- Create: `videomind/app/services/frames.py`
- Create: `videomind/tests/test_frames.py`

**Step 1: Write the failing test**

```python
# tests/test_frames.py
import os
import pytest
from unittest.mock import patch, MagicMock, call
from app.services.frames import extract_frames, deduplicate_frames


@patch("app.services.frames.subprocess.run")
@patch("app.services.frames.os.listdir")
def test_extract_frames_calls_ffmpeg(mock_listdir, mock_run):
    mock_listdir.return_value = ["frame_0001.jpg", "frame_0002.jpg", "frame_0003.jpg"]
    mock_run.return_value = None

    result = extract_frames("/tmp/video.mp4", "/tmp/frames", interval=5)

    assert result == [
        "/tmp/frames/frame_0001.jpg",
        "/tmp/frames/frame_0002.jpg",
        "/tmp/frames/frame_0003.jpg",
    ]
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "ffmpeg" in cmd[0]
    assert "/tmp/video.mp4" in cmd


@patch("app.services.frames.imagehash.average_hash")
@patch("app.services.frames.Image.open")
def test_deduplicate_frames_removes_similar(mock_open, mock_hash):
    # Three frames: first two are identical (hash diff=0), third is different (hash diff=20)
    hash_a = MagicMock()
    hash_b = MagicMock()
    hash_c = MagicMock()

    hash_a.__sub__ = MagicMock(return_value=0)
    hash_b.__sub__ = MagicMock(return_value=0)
    hash_c.__sub__ = MagicMock(return_value=20)

    # First call: hash_a (kept). Second call: hash_b compared to hash_a -> diff 0 (skip).
    # Third call: hash_c compared to hash_a -> diff 20 (keep).
    mock_hash.side_effect = [hash_a, hash_b, hash_c]

    # hash_a - hash_b = 0 (similar, skip frame_b)
    hash_a.__sub__ = MagicMock(side_effect=lambda other: 0 if other is hash_b else 20)

    frames = ["/tmp/frame1.jpg", "/tmp/frame2.jpg", "/tmp/frame3.jpg"]
    result = deduplicate_frames(frames, threshold=5)

    assert len(result) == 2
    assert "/tmp/frame1.jpg" in result
    assert "/tmp/frame3.jpg" in result


@patch("app.services.frames.imagehash.average_hash")
@patch("app.services.frames.Image.open")
def test_deduplicate_frames_keeps_all_when_different(mock_open, mock_hash):
    hash_a = MagicMock()
    hash_b = MagicMock()

    mock_hash.side_effect = [hash_a, hash_b]
    hash_a.__sub__ = MagicMock(return_value=15)

    frames = ["/tmp/frame1.jpg", "/tmp/frame2.jpg"]
    result = deduplicate_frames(frames, threshold=5)

    assert len(result) == 2
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_frames.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write frames.py**

```python
# app/services/frames.py
import os
import subprocess
from PIL import Image
import imagehash


def extract_frames(video_path: str, output_dir: str, interval: int = 5) -> list:
    """Extract one frame every `interval` seconds from a video using FFmpeg."""
    os.makedirs(output_dir, exist_ok=True)

    subprocess.run(
        [
            "ffmpeg", "-i", video_path,
            "-vf", f"fps=1/{interval}",
            "-q:v", "2",
            "-y",
            os.path.join(output_dir, "frame_%04d.jpg")
        ],
        check=True,
        capture_output=True
    )

    frame_files = sorted(
        f for f in os.listdir(output_dir) if f.startswith("frame_") and f.endswith(".jpg")
    )
    return [os.path.join(output_dir, f) for f in frame_files]


def deduplicate_frames(frame_paths: list, threshold: int = 5) -> list:
    """Remove near-duplicate frames using perceptual hashing.

    Compares each frame to the last kept frame. If the hash difference
    is below threshold, the frame is considered a duplicate and skipped.
    """
    if not frame_paths:
        return []

    kept = [frame_paths[0]]
    last_hash = imagehash.average_hash(Image.open(frame_paths[0]))

    for path in frame_paths[1:]:
        current_hash = imagehash.average_hash(Image.open(path))
        diff = last_hash - current_hash
        if diff > threshold:
            kept.append(path)
            last_hash = current_hash

    return kept
```

**Step 4: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_frames.py -v`
Expected: PASS

**Step 5: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add app/services/frames.py tests/test_frames.py
git commit -m "feat: frame extraction with smart deduplication"
```

---

### Task 3: Vision Analysis Service

**Files:**
- Create: `videomind/app/services/vision.py`
- Create: `videomind/tests/test_vision.py`

**Step 1: Write the failing test**

```python
# tests/test_vision.py
import pytest
from unittest.mock import patch, MagicMock, mock_open
from app.services.vision import analyze_frame, analyze_frames
import base64


@patch("builtins.open", mock_open(read_data=b"fake image data"))
@patch("app.services.vision.openai.OpenAI")
def test_analyze_frame_returns_description(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = "A terminal window showing Docker commands"

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_response

    result = analyze_frame("/tmp/frame_0001.jpg")

    assert result == "A terminal window showing Docker commands"
    mock_client.chat.completions.create.assert_called_once()


@patch("app.services.vision.analyze_frame")
def test_analyze_frames_processes_all(mock_analyze):
    mock_analyze.side_effect = ["Description 1", "Description 2"]

    frames = [
        {"path": "/tmp/frame_0001.jpg", "timestamp": 5.0},
        {"path": "/tmp/frame_0002.jpg", "timestamp": 10.0},
    ]

    result = analyze_frames(frames)

    assert len(result) == 2
    assert result[0]["description"] == "Description 1"
    assert result[0]["timestamp"] == 5.0
    assert result[1]["description"] == "Description 2"
    assert result[1]["timestamp"] == 10.0


@patch("app.services.vision.analyze_frame")
def test_analyze_frames_handles_failure_gracefully(mock_analyze):
    mock_analyze.side_effect = [Exception("API error"), "Description 2"]

    frames = [
        {"path": "/tmp/frame_0001.jpg", "timestamp": 5.0},
        {"path": "/tmp/frame_0002.jpg", "timestamp": 10.0},
    ]

    result = analyze_frames(frames)

    assert len(result) == 2
    assert result[0]["description"] == "Analysis failed"
    assert result[1]["description"] == "Description 2"
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_vision.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write vision.py**

```python
# app/services/vision.py
import base64
import openai
from app.config import OPENAI_API_KEY


def analyze_frame(frame_path: str) -> str:
    """Send a single frame to GPT-4o Vision and get a description."""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    with open(frame_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You describe video frames concisely. Focus on what is visually "
                    "shown: text on screen, UI elements, diagrams, code, people, "
                    "actions. One sentence, max 50 words."
                )
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}",
                            "detail": "low"
                        }
                    },
                    {
                        "type": "text",
                        "text": "Describe what is shown in this video frame."
                    }
                ]
            }
        ],
        max_tokens=100,
        temperature=0.2
    )

    return response.choices[0].message.content.strip()


def analyze_frames(frames: list) -> list:
    """Analyze a list of frames with GPT-4o Vision.

    Args:
        frames: List of dicts with "path" and "timestamp" keys.

    Returns:
        List of dicts with "timestamp", "frame_path", and "description" keys.
    """
    results = []
    for frame in frames:
        try:
            description = analyze_frame(frame["path"])
        except Exception:
            description = "Analysis failed"

        results.append({
            "timestamp": frame["timestamp"],
            "frame_path": frame["path"],
            "description": description
        })

    return results
```

**Step 4: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_vision.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/vision.py tests/test_vision.py
git commit -m "feat: GPT-4o Vision frame analysis service"
```

---

### Task 4: Update Database Schema for Visual Data

**Files:**
- Modify: `videomind/app/database.py` — add visual_analysis column
- Modify: `videomind/tests/test_database.py` — add test for new column

**Step 1: Write the failing test**

Add to the end of `videomind/tests/test_database.py`:

```python
def test_job_stores_visual_analysis():
    job_id = create_job(TEST_DB, url="https://youtube.com/watch?v=test", options={})
    update_job_status(
        TEST_DB, job_id,
        visual_analysis='[{"timestamp": 5.0, "description": "A code editor"}]'
    )
    job = get_job(TEST_DB, job_id)
    assert '"timestamp": 5.0' in job["visual_analysis"]
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_database.py::test_job_stores_visual_analysis -v`
Expected: FAIL — column doesn't exist

**Step 3: Add visual_analysis column to database schema**

In `videomind/app/database.py`, add the column to the CREATE TABLE statement. The new column goes after `subtitles_srt`:

```
visual_analysis TEXT DEFAULT '[]',
```

**Step 4: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_database.py -v`
Expected: ALL PASS

**Step 5: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add app/database.py tests/test_database.py
git commit -m "feat: add visual_analysis column to jobs table"
```

---

### Task 5: Update Pipeline with Vision Steps

**Files:**
- Modify: `videomind/app/workers/pipeline.py` — add frame extraction + vision analysis steps
- Modify: `videomind/tests/test_pipeline.py` — update existing test, add vision pipeline test

**Step 1: Write the failing test**

Add to `videomind/tests/test_pipeline.py`:

```python
@patch("app.workers.pipeline.analyze_frames")
@patch("app.workers.pipeline.deduplicate_frames")
@patch("app.workers.pipeline.extract_frames")
@patch("app.workers.pipeline.summarize_transcript")
@patch("app.workers.pipeline.transcribe_audio")
@patch("app.workers.pipeline.extract_audio")
@patch("app.workers.pipeline.download_video")
def test_pipeline_with_visual_analysis(
    mock_download, mock_audio, mock_transcribe, mock_summarize,
    mock_extract_frames, mock_dedup, mock_analyze_frames
):
    mock_download.return_value = {
        "title": "Test Video", "duration": 120,
        "source": "youtube", "file_path": "/tmp/test.mp4"
    }
    mock_audio.return_value = "/tmp/test.wav"
    mock_transcribe.return_value = {
        "full_text": "Hello world",
        "segments": [{"start": 0.0, "end": 5.0, "text": "Hello world"}]
    }
    mock_summarize.return_value = {
        "short": "A greeting.", "detailed": "The video contains a greeting.",
        "chapters": [{"start": "0:00", "end": "0:05", "title": "Greeting"}]
    }
    mock_extract_frames.return_value = ["/tmp/frames/frame_0001.jpg", "/tmp/frames/frame_0002.jpg"]
    mock_dedup.return_value = ["/tmp/frames/frame_0001.jpg"]
    mock_analyze_frames.return_value = [
        {"timestamp": 5.0, "frame_path": "/tmp/frames/frame_0001.jpg", "description": "A terminal window"}
    ]

    job_id = create_job(TEST_DB, url="https://youtube.com/watch?v=test", options={"visual_analysis": True})
    process_video(job_id, TEST_DB)

    job = get_job(TEST_DB, job_id)
    assert job["status"] == "completed"
    assert "terminal window" in job["visual_analysis"]
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_pipeline.py::test_pipeline_with_visual_analysis -v`
Expected: FAIL — new imports don't exist in pipeline

**Step 3: Update pipeline.py to include vision steps**

Replace the full contents of `videomind/app/workers/pipeline.py`:

```python
# app/workers/pipeline.py
import os
import json
from app.models import get_job, update_job_status
from app.services.downloader import download_video
from app.services.audio import extract_audio
from app.services.transcriber import transcribe_audio
from app.services.summarizer import summarize_transcript
from app.services.frames import extract_frames, deduplicate_frames
from app.services.vision import analyze_frames
from app.config import TEMP_DIR, FRAMES_DIR


def process_video(job_id: str, db_path: str = None):
    from app.config import DATABASE_URL
    db = db_path or DATABASE_URL

    try:
        job = get_job(db, job_id)
        if job is None:
            return

        options = json.loads(job["options"]) if isinstance(job["options"], str) else job["options"]
        temp_dir = os.path.join(TEMP_DIR, job_id)
        os.makedirs(temp_dir, exist_ok=True)

        # Step 1: Download video
        update_job_status(db, job_id, status="processing", progress=10, step="Downloading video...")
        video_info = download_video(job["url"], temp_dir)

        update_job_status(
            db, job_id, progress=20, step="Extracting audio...",
            video_title=video_info["title"],
            video_duration=str(video_info["duration"]),
            video_source=video_info["source"]
        )

        # Step 2: Extract audio
        audio_path = extract_audio(video_info["file_path"], temp_dir)
        update_job_status(db, job_id, progress=30, step="Transcribing audio...")

        # Step 3: Transcribe
        transcript = transcribe_audio(audio_path)
        update_job_status(
            db, job_id, progress=50, step="Generating summary...",
            transcript_text=transcript["full_text"],
            transcript_segments=json.dumps(transcript["segments"])
        )

        # Step 4: Summarize
        summary = summarize_transcript(transcript["full_text"])

        # Step 5: Generate SRT subtitles
        srt = generate_srt(transcript["segments"])

        # Step 6: Visual analysis (if requested)
        visual_analysis = []
        if options.get("visual_analysis", False):
            update_job_status(db, job_id, progress=60, step="Extracting frames...")

            frames_dir = os.path.join(FRAMES_DIR, job_id)
            raw_frames = extract_frames(video_info["file_path"], frames_dir, interval=5)

            update_job_status(db, job_id, progress=70, step="Deduplicating frames...")
            unique_frames = deduplicate_frames(raw_frames, threshold=5)

            # Build frame list with timestamps (frame index * interval seconds)
            frame_list = []
            for i, path in enumerate(unique_frames):
                # Estimate timestamp from frame filename (frame_NNNN.jpg)
                basename = os.path.basename(path)
                frame_num = int(basename.replace("frame_", "").replace(".jpg", ""))
                timestamp = (frame_num - 1) * 5  # 0-indexed, 5s interval
                frame_list.append({"path": path, "timestamp": float(timestamp)})

            update_job_status(db, job_id, progress=80, step="Analyzing frames with AI...")
            visual_analysis = analyze_frames(frame_list)

        # Step 7: Mark complete
        update_job_status(
            db, job_id,
            status="completed",
            progress=100,
            step="Done",
            summary_short=summary["short"],
            summary_detailed=summary["detailed"],
            chapters=json.dumps(summary["chapters"]),
            subtitles_srt=srt,
            visual_analysis=json.dumps(visual_analysis)
        )

    except Exception as e:
        update_job_status(
            db, job_id,
            status="failed",
            step="Error",
            error_message=str(e)
        )

    finally:
        _cleanup_temp(temp_dir if 'temp_dir' in dir() else None)


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


def _cleanup_temp(temp_dir):
    if temp_dir is None:
        return
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

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_pipeline.py -v`
Expected: ALL PASS

**Step 5: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add app/workers/pipeline.py tests/test_pipeline.py
git commit -m "feat: integrate frame extraction and vision analysis into pipeline"
```

---

### Task 6: Update Results Endpoint for Visual Data

**Files:**
- Modify: `videomind/app/routers/results.py` — add visual_analysis to result response
- Modify: `videomind/tests/test_endpoints.py` — add test for visual data in result

**Step 1: Write the failing test**

Add to `videomind/tests/test_endpoints.py`:

```python
def test_result_includes_visual_analysis():
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
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_endpoints.py::test_result_includes_visual_analysis -v`
Expected: FAIL — visual_analysis not in response

**Step 3: Update results.py to include visual_analysis**

In `videomind/app/routers/results.py`, add to the completed result response (inside the `get_result` function's final return dict), after `"subtitles_srt"`:

```python
"visual_analysis": json.loads(job["visual_analysis"] or "[]"),
```

**Step 4: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_endpoints.py -v`
Expected: ALL PASS

**Step 5: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 6: Commit**

```bash
git add app/routers/results.py tests/test_endpoints.py
git commit -m "feat: include visual_analysis in result endpoint response"
```

---

### Task 7: Q&A Service

**Files:**
- Create: `videomind/app/services/qa.py`
- Create: `videomind/tests/test_qa.py`

**Step 1: Write the failing test**

```python
# tests/test_qa.py
import pytest
from unittest.mock import patch, MagicMock
from app.services.qa import answer_question


@patch("app.services.qa.openai.OpenAI")
def test_answer_question_returns_answer(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = '{"answer": "He ran docker pull nginx at 5:02.", "relevant_timestamps": ["5:02"], "relevant_frames": []}'

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_response

    result = answer_question(
        question="What command was run?",
        transcript="At 5:02 he ran docker pull nginx",
        visual_analysis=[],
        chapters=[]
    )

    assert "docker pull nginx" in result["answer"]
    assert "5:02" in result["relevant_timestamps"]


@patch("app.services.qa.openai.OpenAI")
def test_answer_question_includes_visual_context(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = '{"answer": "A Docker architecture diagram is shown.", "relevant_timestamps": ["1:15"], "relevant_frames": ["/frames/frame_015.jpg"]}'

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_response

    result = answer_question(
        question="What diagram is shown?",
        transcript="Let me show you the architecture",
        visual_analysis=[{"timestamp": 75.0, "description": "Docker architecture diagram"}],
        chapters=[]
    )

    assert "diagram" in result["answer"]
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_qa.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write qa.py**

```python
# app/services/qa.py
import json
import openai
from app.config import OPENAI_API_KEY


def answer_question(question: str, transcript: str, visual_analysis: list, chapters: list) -> dict:
    """Answer a question about a processed video using transcript and visual context."""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    # Build context from visual analysis
    visual_context = ""
    if visual_analysis:
        visual_lines = []
        for frame in visual_analysis:
            ts = frame.get("timestamp", 0)
            desc = frame.get("description", "")
            visual_lines.append(f"[{_seconds_to_timestamp(ts)}] {desc}")
        visual_context = "\n\nVisual observations:\n" + "\n".join(visual_lines)

    chapter_context = ""
    if chapters:
        chapter_lines = [f"- {ch.get('start', '')} to {ch.get('end', '')}: {ch.get('title', '')}" for ch in chapters]
        chapter_context = "\n\nChapters:\n" + "\n".join(chapter_lines)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "You answer questions about videos based on their transcript and visual analysis. "
                    "Return a JSON object with:\n"
                    '- "answer": Your answer to the question (2-3 sentences)\n'
                    '- "relevant_timestamps": Array of relevant timestamp strings (e.g., ["5:02", "5:15"])\n'
                    '- "relevant_frames": Array of frame paths if visual frames are relevant, else empty array\n'
                    "Return ONLY valid JSON, no markdown."
                )
            },
            {
                "role": "user",
                "content": f"Transcript:\n{transcript[:6000]}{visual_context}{chapter_context}\n\nQuestion: {question}"
            }
        ],
        temperature=0.3,
        max_tokens=500
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    data = json.loads(raw)

    return {
        "answer": data.get("answer", ""),
        "relevant_timestamps": data.get("relevant_timestamps", []),
        "relevant_frames": data.get("relevant_frames", [])
    }


def _seconds_to_timestamp(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"
```

**Step 4: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_qa.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/qa.py tests/test_qa.py
git commit -m "feat: Q&A service for asking questions about videos"
```

---

### Task 8: Q&A Endpoint

**Files:**
- Create: `videomind/app/routers/ask.py`
- Create: `videomind/tests/test_ask.py`
- Modify: `videomind/app/main.py` — add ask router

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_ask.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write ask.py router**

```python
# app/routers/ask.py
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.models import get_job
from app.services.qa import answer_question
from app.config import DATABASE_URL

router = APIRouter()


class AskRequest(BaseModel):
    job_id: str
    question: str


@router.post("/api/v1/ask")
def ask_about_video(request: AskRequest):
    job = get_job(DATABASE_URL, request.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video processing not yet completed")

    visual_analysis = json.loads(job["visual_analysis"] or "[]")
    chapters = json.loads(job["chapters"] or "[]")

    result = answer_question(
        question=request.question,
        transcript=job["transcript_text"],
        visual_analysis=visual_analysis,
        chapters=chapters
    )

    return result
```

**Step 4: Update main.py to include ask router**

In `videomind/app/main.py`, add the import and include the router:

Add to imports: `from app.routers import analyze, results, ask`
Add after `app.include_router(results.router)`: `app.include_router(ask.router)`

**Step 5: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_ask.py -v`
Expected: PASS

**Step 6: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add app/routers/ask.py tests/test_ask.py app/main.py
git commit -m "feat: POST /api/v1/ask endpoint for Q&A over video content"
```

---

### Task 9: Blog Writer Service

**Files:**
- Create: `videomind/app/services/blog_writer.py`
- Create: `videomind/tests/test_blog_writer.py`

**Step 1: Write the failing test**

```python
# tests/test_blog_writer.py
import pytest
from unittest.mock import patch, MagicMock
from app.services.blog_writer import generate_blog


@patch("app.services.blog_writer.openai.OpenAI")
def test_generate_blog_returns_markdown(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = '{"title": "Docker Tutorial: A Complete Guide", "content_markdown": "# Docker Tutorial\\n\\n## Introduction\\n\\nThis tutorial covers Docker basics.", "image_suggestions": [{"timestamp": 5.0, "caption": "Docker architecture", "insert_after": "## Architecture"}]}'

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_response

    result = generate_blog(
        transcript="This is a Docker tutorial...",
        summary="A Docker tutorial covering basics.",
        chapters=[{"start": "0:00", "end": "5:00", "title": "Introduction"}],
        visual_analysis=[{"timestamp": 5.0, "description": "Architecture diagram"}],
        style="tutorial"
    )

    assert result["title"] == "Docker Tutorial: A Complete Guide"
    assert "# Docker Tutorial" in result["content_markdown"]
    assert len(result["image_suggestions"]) == 1


@patch("app.services.blog_writer.openai.OpenAI")
def test_generate_blog_handles_no_visuals(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client

    mock_message = MagicMock()
    mock_message.content = '{"title": "Test Blog", "content_markdown": "# Test\\n\\nContent.", "image_suggestions": []}'

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    mock_client.chat.completions.create.return_value = mock_response

    result = generate_blog(
        transcript="Simple transcript.",
        summary="A simple video.",
        chapters=[],
        visual_analysis=[],
        style="article"
    )

    assert result["title"] == "Test Blog"
    assert result["image_suggestions"] == []
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_blog_writer.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write blog_writer.py**

```python
# app/services/blog_writer.py
import json
import openai
from app.config import OPENAI_API_KEY


def generate_blog(
    transcript: str,
    summary: str,
    chapters: list,
    visual_analysis: list,
    style: str = "article"
) -> dict:
    """Convert video content into a blog article."""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    chapter_text = ""
    if chapters:
        chapter_lines = [f"- {ch.get('start', '')} to {ch.get('end', '')}: {ch.get('title', '')}" for ch in chapters]
        chapter_text = "\n\nChapters:\n" + "\n".join(chapter_lines)

    visual_text = ""
    if visual_analysis:
        visual_lines = [f"- [{v.get('timestamp', 0)}s] {v.get('description', '')}" for v in visual_analysis]
        visual_text = "\n\nVisual scenes:\n" + "\n".join(visual_lines)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You convert video transcripts into well-structured blog articles in '{style}' style. "
                    "Return a JSON object with:\n"
                    '- "title": A compelling blog title\n'
                    '- "content_markdown": The full article in markdown format, using the transcript content '
                    "to write a comprehensive article with headers, paragraphs, code blocks if relevant, and lists.\n"
                    '- "image_suggestions": Array of objects with "timestamp" (float), "caption" (string), '
                    'and "insert_after" (markdown heading where the image fits best). '
                    "Only suggest images where visual frames were available.\n"
                    "Return ONLY valid JSON, no markdown wrapping."
                )
            },
            {
                "role": "user",
                "content": (
                    f"Summary: {summary}\n\n"
                    f"Transcript:\n{transcript[:8000]}"
                    f"{chapter_text}{visual_text}"
                )
            }
        ],
        temperature=0.4,
        max_tokens=3000
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    data = json.loads(raw)

    return {
        "title": data.get("title", ""),
        "content_markdown": data.get("content_markdown", ""),
        "image_suggestions": data.get("image_suggestions", [])
    }
```

**Step 4: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_blog_writer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/blog_writer.py tests/test_blog_writer.py
git commit -m "feat: blog writer service for video-to-blog conversion"
```

---

### Task 10: Blog Endpoint

**Files:**
- Create: `videomind/app/routers/blog.py`
- Create: `videomind/tests/test_blog.py`
- Modify: `videomind/app/main.py` — add blog router

**Step 1: Write the failing test**

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_blog.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write blog.py router**

```python
# app/routers/blog.py
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.models import get_job
from app.services.blog_writer import generate_blog
from app.config import DATABASE_URL

router = APIRouter()


class BlogRequest(BaseModel):
    job_id: str
    style: Optional[str] = "article"
    include_images: Optional[bool] = True


@router.post("/api/v1/to-blog")
def video_to_blog(request: BlogRequest):
    job = get_job(DATABASE_URL, request.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Video processing not yet completed")

    visual_analysis = json.loads(job["visual_analysis"] or "[]") if request.include_images else []
    chapters = json.loads(job["chapters"] or "[]")

    result = generate_blog(
        transcript=job["transcript_text"],
        summary=job["summary_short"],
        chapters=chapters,
        visual_analysis=visual_analysis,
        style=request.style
    )

    return result
```

**Step 4: Update main.py to include blog router**

In `videomind/app/main.py`, update the import and add the router:

Add to imports: `from app.routers import analyze, results, ask, blog`
Add after `app.include_router(ask.router)`: `app.include_router(blog.router)`

**Step 5: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_blog.py -v`
Expected: PASS

**Step 6: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add app/routers/blog.py tests/test_blog.py app/main.py
git commit -m "feat: POST /api/v1/to-blog endpoint for video-to-blog conversion"
```

---

### Task 11: Phase 2 End-to-End Test

**Files:**
- Create: `videomind/tests/test_e2e_phase2.py`

**Step 1: Write e2e test**

```python
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
```

**Step 2: Run e2e test**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_e2e_phase2.py -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add tests/test_e2e_phase2.py
git commit -m "test: end-to-end test for Phase 2 vision + Q&A + blog features"
```

---

### Phase 2 Complete Checklist

After all tasks are done, verify:

- [ ] `python -m pytest tests/ -v` — all tests pass (Phase 1 + Phase 2)
- [ ] `python -m uvicorn app.main:app --port 8000` — server starts
- [ ] `GET /api/v1/health` — returns healthy
- [ ] `POST /api/v1/analyze` with `{"visual_analysis": true}` — triggers frame extraction + vision
- [ ] `GET /api/v1/result/{job_id}` — includes `visual_analysis` array
- [ ] `POST /api/v1/ask` — returns answer with timestamps
- [ ] `POST /api/v1/to-blog` — returns blog article with markdown

### What's Next (Phase 3)

Phase 3 adds:
1. User registration endpoint
2. API key generation
3. Stripe integration (subscriptions)
4. Tier-based rate limiting
5. Usage tracking endpoint
6. Stripe webhook handling
