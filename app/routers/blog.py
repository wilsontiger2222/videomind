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
