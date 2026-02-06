from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
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
