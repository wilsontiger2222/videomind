# app/middleware/auth.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import API_KEYS, DATABASE_URL
from app.models import get_user_by_api_key

PUBLIC_PATHS = ["/api/v1/health", "/api/v1/register", "/api/v1/stripe/webhook", "/docs", "/openapi.json", "/redoc"]


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        is_public = request.url.path in PUBLIC_PATHS

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            if is_public:
                return await call_next(request)
            return JSONResponse(
                status_code=401, content={"detail": "Missing API key"}
            )

        if not auth_header.startswith("Bearer "):
            if is_public:
                return await call_next(request)
            return JSONResponse(
                status_code=401, content={"detail": "Invalid API key format"}
            )

        api_key = auth_header.replace("Bearer ", "")

        # Check legacy env-based keys first (backwards compat for testing)
        if api_key in API_KEYS:
            request.state.user = {"plan": "business", "api_key": api_key, "id": "legacy"}
            return await call_next(request)

        # Check database-backed keys
        user = get_user_by_api_key(DATABASE_URL, api_key)
        if user is None:
            if is_public:
                return await call_next(request)
            return JSONResponse(
                status_code=401, content={"detail": "Invalid API key"}
            )

        request.state.user = user
        return await call_next(request)
