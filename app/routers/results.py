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
        "subtitles_srt": job["subtitles_srt"],
        "visual_analysis": json.loads(job["visual_analysis"] or "[]")
    }
