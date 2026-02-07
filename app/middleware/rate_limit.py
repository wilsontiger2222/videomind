# app/middleware/rate_limit.py
import time
from collections import defaultdict
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import DATABASE_URL

# In-memory rate limit tracker: {api_key: [(timestamp, ...), ...]}
_request_log = defaultdict(list)

PLAN_RATE_LIMITS = {
    "free": 10,
    "pro": 100,
    "business": 500,
}

PUBLIC_PATHS = ["/api/v1/register", "/api/v1/stripe/webhook", "/docs", "/openapi.json", "/redoc"]


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # User is attached by auth middleware (runs before this)
        user = getattr(request.state, "user", None)
        if user is None:
            return await call_next(request)

        api_key = user.get("api_key", "")
        plan = user.get("plan", "free")
        limit = PLAN_RATE_LIMITS.get(plan, 10)

        now = time.time()
        one_hour_ago = now - 3600

        # Clean old entries and count recent requests
        _request_log[api_key] = [t for t in _request_log[api_key] if t > one_hour_ago]

        if len(_request_log[api_key]) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded. {plan} plan allows {limit} requests per hour."}
            )

        _request_log[api_key].append(now)
        return await call_next(request)
