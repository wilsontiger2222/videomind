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
