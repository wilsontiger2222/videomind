from fastapi import FastAPI
from app.database import init_db
from app.routers import analyze, results, ask, blog, auth, stripe_webhook, usage, admin
from app.middleware.auth import APIKeyMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

app = FastAPI(
    title="VideoMind API",
    description="Turn any video into text, summaries, and insights",
    version="0.1.0"
)

app.add_middleware(RateLimitMiddleware)
app.add_middleware(APIKeyMiddleware)
app.include_router(analyze.router)
app.include_router(results.router)
app.include_router(ask.router)
app.include_router(blog.router)
app.include_router(auth.router)
app.include_router(stripe_webhook.router)
app.include_router(usage.router)
app.include_router(admin.router)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "VideoMind API"
    }
