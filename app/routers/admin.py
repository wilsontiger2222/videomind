# app/routers/admin.py
from fastapi import APIRouter, Request, HTTPException
from app.config import DATABASE_URL
from app.services.health import check_system_health
from app.services.report import generate_daily_stats

router = APIRouter()


@router.get("/api/v1/admin/stats")
def get_admin_stats(request: Request):
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    health = check_system_health(DATABASE_URL)
    stats = generate_daily_stats(DATABASE_URL)

    return {
        "health": health,
        "stats": stats,
    }
