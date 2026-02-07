# app/routers/usage.py
from fastapi import APIRouter, Request, HTTPException
from app.models import get_user_usage
from app.config import DATABASE_URL

router = APIRouter()


@router.get("/api/v1/usage")
def get_usage(request: Request):
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Legacy keys return hardcoded business usage
    if user.get("id") == "legacy":
        return {
            "plan": "business",
            "videos_today": 0,
            "videos_limit": 150,
            "requests_limit": 500,
        }

    usage = get_user_usage(DATABASE_URL, user["api_key"])
    if usage is None:
        raise HTTPException(status_code=404, detail="User not found")

    return usage
