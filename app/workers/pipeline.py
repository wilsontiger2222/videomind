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
