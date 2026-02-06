from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import API_KEYS

PUBLIC_PATHS = ["/api/v1/health", "/docs", "/openapi.json", "/redoc"]


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                status_code=401, content={"detail": "Missing API key"}
            )

        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401, content={"detail": "Invalid API key format"}
            )

        api_key = auth_header.replace("Bearer ", "")
        if api_key not in API_KEYS:
            return JSONResponse(
                status_code=401, content={"detail": "Invalid API key"}
            )

        return await call_next(request)
