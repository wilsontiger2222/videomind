# app/routers/auth.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.models import create_user
from app.config import DATABASE_URL

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    password: str


@router.post("/api/v1/register")
def register_user(request: RegisterRequest):
    if len(request.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    try:
        result = create_user(DATABASE_URL, email=request.email, password=request.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result
