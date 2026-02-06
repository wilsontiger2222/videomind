from fastapi import FastAPI
from app.database import init_db

app = FastAPI(
    title="VideoMind API",
    description="Turn any video into text, summaries, and insights",
    version="0.1.0"
)

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
