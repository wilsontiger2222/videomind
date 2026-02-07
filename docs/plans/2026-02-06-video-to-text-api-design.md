# VideoMind API — Full Design Document

## Overview

**Product:** VideoMind API — A hosted API that lets AI agents and developers "watch" and understand any video by extracting both audio (transcript) and visual (frame analysis) information.

**Problem:** No AI model can natively watch a video. AI users constantly hit this wall when working with YouTube tutorials, presentations, coding videos, product demos, etc.

**Solution:** Send a video URL to the API, get back a full transcript, visual scene descriptions, summary, chapters, key frames, subtitles, and the ability to ask questions about the video.

**Target audience:** AI/ChatGPT power users, developers building AI agents, content creators who need video-to-text workflows.

**Business model:** Freemium SaaS with monthly subscriptions via Stripe.

---

## Architecture

### High-Level Flow

```
User/AI Agent                     DigitalOcean Server
     |                                    |
     |  POST /api/v1/analyze              |
     |  { "url": "youtube.com/..." }      |
     | ---------------------------------> |
     |                                    |
     |  { "job_id": "abc123" }            |
     | <--------------------------------- |
     |                                    |
     |         (Background Processing)    |
     |                                    |  1. yt-dlp downloads video
     |                                    |  2. FFmpeg extracts audio
     |                                    |  3. FFmpeg extracts key frames
     |                                    |  4. Whisper transcribes audio
     |                                    |  5. GPT-4o Vision analyzes frames
     |                                    |  6. GPT-4o generates summary/chapters
     |                                    |  7. Results saved to database
     |                                    |
     |  GET /api/v1/result/abc123         |
     |  { "transcript": "...",            |
     |    "visual_analysis": [...],       |
     |    "summary": "...",               |
     |    "chapters": [...] }             |
     | <--------------------------------- |
```

### Component Diagram

```
                    ┌─────────────────────────────────┐
                    │        DigitalOcean Droplet      │
                    │                                   │
 User Request ───>  │  ┌──────────┐    ┌────────────┐  │
                    │  │ FastAPI   │───>│ Redis       │  │
                    │  │ (Web App) │    │ (Job Queue) │  │
                    │  └──────────┘    └─────┬──────┘  │
                    │                        │         │
                    │                  ┌─────▼──────┐  │
                    │                  │ Celery      │  │
                    │                  │ (Workers)   │  │
                    │                  └─────┬──────┘  │
                    │                        │         │
                    │  ┌─────────┬───────┬───┴──────┐  │
                    │  │ yt-dlp  │FFmpeg │ Whisper  │  │
                    │  │         │       │ (local)  │  │
                    │  └─────────┴───────┴──────────┘  │
                    │                                   │
                    │  ┌──────────┐    ┌────────────┐  │
                    │  │ SQLite   │    │ File Store │  │
                    │  │ (Database)│    │ (frames/   │  │
                    │  │          │    │  audio)    │  │
                    │  └──────────┘    └────────────┘  │
                    └─────────────────────────────────┘
                              │              │
                    ┌─────────▼──┐    ┌─────▼──────┐
                    │ Stripe API │    │ OpenAI API │
                    │ (Payments) │    │ (Vision +  │
                    │            │    │  Text)     │
                    └────────────┘    └────────────┘
```

---

## API Endpoints

### Authentication

All requests require an API key in the header:
```
Authorization: Bearer sk_live_abc123xyz
```

### Core Endpoints

#### POST /api/v1/analyze
Submit a video for processing.

**Request:**
```json
{
  "url": "https://www.youtube.com/watch?v=example",
  "options": {
    "transcript": true,
    "visual_analysis": true,
    "summary": true,
    "chapters": true,
    "key_frames": true,
    "subtitles": true
  }
}
```

**Response:**
```json
{
  "job_id": "job_abc123",
  "status": "processing",
  "estimated_time_seconds": 120
}
```

#### GET /api/v1/status/{job_id}
Check processing status.

**Response:**
```json
{
  "job_id": "job_abc123",
  "status": "processing",
  "progress": 65,
  "step": "Analyzing visual frames..."
}
```

#### GET /api/v1/result/{job_id}
Get full results.

**Response:**
```json
{
  "job_id": "job_abc123",
  "status": "completed",
  "video": {
    "title": "Docker Tutorial for Beginners",
    "duration": "10:32",
    "source": "youtube.com"
  },
  "transcript": {
    "full_text": "Welcome to this Docker tutorial...",
    "segments": [
      {
        "start": 0.0,
        "end": 5.2,
        "text": "Welcome to this Docker tutorial"
      }
    ]
  },
  "visual_analysis": [
    {
      "timestamp": "0:32",
      "frame_url": "/frames/job_abc123/frame_032.jpg",
      "description": "Terminal window showing 'docker pull nginx' command"
    },
    {
      "timestamp": "1:15",
      "frame_url": "/frames/job_abc123/frame_075.jpg",
      "description": "Architecture diagram showing three containers connected to a load balancer"
    }
  ],
  "summary": {
    "short": "A beginner Docker tutorial covering installation, basic commands, and container deployment.",
    "detailed": "This tutorial walks through Docker from scratch..."
  },
  "chapters": [
    {"start": "0:00", "end": "1:30", "title": "Introduction"},
    {"start": "1:30", "end": "4:00", "title": "Installing Docker"},
    {"start": "4:00", "end": "7:00", "title": "Basic Docker Commands"},
    {"start": "7:00", "end": "10:32", "title": "Deploying Your First Container"}
  ],
  "subtitles_srt": "1\n00:00:00,000 --> 00:00:05,200\nWelcome to this Docker tutorial\n\n...",
  "key_frames": [
    "/frames/job_abc123/frame_032.jpg",
    "/frames/job_abc123/frame_075.jpg",
    "/frames/job_abc123/frame_120.jpg"
  ]
}
```

#### POST /api/v1/ask
Ask a question about a processed video.

**Request:**
```json
{
  "job_id": "job_abc123",
  "question": "What Docker command did he run at the 5 minute mark?"
}
```

**Response:**
```json
{
  "answer": "At around 5:02, the presenter ran 'docker run -d -p 80:80 nginx' to start an Nginx container in detached mode, mapping port 80.",
  "relevant_timestamps": ["4:58", "5:02", "5:15"],
  "relevant_frames": ["/frames/job_abc123/frame_302.jpg"]
}
```

#### POST /api/v1/to-blog
Convert a processed video into a blog article.

**Request:**
```json
{
  "job_id": "job_abc123",
  "style": "tutorial",
  "include_images": true
}
```

**Response:**
```json
{
  "title": "Docker Tutorial for Beginners: A Complete Guide",
  "content_markdown": "# Docker Tutorial for Beginners\n\n## Introduction\n\n...",
  "images": [
    {
      "url": "/frames/job_abc123/frame_075.jpg",
      "caption": "Docker architecture overview",
      "insert_after": "## Architecture"
    }
  ]
}
```

### User Management Endpoints

#### POST /api/v1/register
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```
Returns: API key + Stripe checkout link for upgrading.

#### GET /api/v1/usage
Check current usage and limits.
```json
{
  "plan": "pro",
  "videos_today": 12,
  "videos_limit": 30,
  "requests_this_hour": 45,
  "requests_limit": 100
}
```

---

## Tech Stack

| Component | Technology | Purpose | Cost |
|-----------|-----------|---------|------|
| Web Framework | FastAPI (Python) | Handles all API requests | Free |
| Video Download | yt-dlp | Downloads from YouTube + 1000 sites | Free |
| Video Processing | FFmpeg | Extracts audio, pulls frames | Free |
| Speech-to-Text | OpenAI Whisper (local) | Transcription — runs on server | Free |
| Vision Analysis | GPT-4o Vision API | Describes what's in video frames | ~$0.01-0.03/frame |
| Text AI | GPT-4o API | Summaries, chapters, Q&A, blog | ~$0.01-0.05/video |
| Database | SQLite | Users, jobs, results, usage tracking | Free |
| Job Queue | Celery + Redis | Background video processing | Free |
| Payments | Stripe API | Subscriptions, checkout, webhooks | 2.9% per txn |
| Email | SendGrid API | Welcome emails, support, reports | Free tier: 100/day |
| Server | DigitalOcean Droplet | Hosts everything | $24-48/mo |

### Smart Frame Extraction (Cost Optimization)

To avoid analyzing 100s of duplicate frames:
1. Extract one frame every 5 seconds
2. Compare consecutive frames for similarity (pixel hash)
3. Skip frames that are nearly identical (same slide, same screen)
4. Only send UNIQUE/CHANGED frames to GPT-4o Vision
5. Result: A 10-min video might only need 15-30 frames analyzed instead of 120

This keeps vision API costs low (~$0.15-0.45 per video instead of $1.20+).

---

## Pricing & Tiers

| Feature | Free | Pro $12/mo | Business $39/mo |
|---------|------|-----------|----------------|
| Videos per day | 3 | 30 | 150 |
| Max video length | 10 min | 60 min | 3 hours |
| Audio transcript | Yes | Yes | Yes |
| Visual analysis | No | Yes | Yes |
| Summary | Yes | Yes | Yes |
| Chapters | Yes | Yes | Yes |
| Q&A over video | No | Yes | Yes |
| Video-to-blog | No | No | Yes |
| Subtitle export | Yes | Yes | Yes |
| Key frame images | No | Yes | Yes |
| API rate limit | 10/hour | 100/hour | 500/hour |
| Support | None | Email | Priority email |

### Unit Economics

| Metric | Value |
|--------|-------|
| Average cost per video (audio only) | ~$0.02 |
| Average cost per video (audio + vision) | ~$0.10-0.20 |
| Pro user processes ~20 videos/month | Cost: ~$2-4/mo |
| Pro user pays | $12/mo |
| **Gross margin per Pro user** | **~$8-10/mo (70-80%)** |
| Business user processes ~80 videos/month | Cost: ~$8-16/mo |
| Business user pays | $39/mo |
| **Gross margin per Business user** | **~$23-31/mo (60-80%)** |
| Server cost | $24-48/mo |
| **Break-even** | **~5 Pro users or 2 Business users** |

---

## Server Requirements

### Recommended DigitalOcean Droplet

**Starting (0-50 users):**
- 4GB RAM / 2 vCPU / 80GB SSD — $24/mo
- Handles Whisper "small" model
- ~50 videos/day capacity

**Growth (50-500 users):**
- 8GB RAM / 4 vCPU / 160GB SSD — $48/mo
- Handles Whisper "medium" model (better accuracy)
- ~200 videos/day capacity

**Scale (500+ users):**
- 16GB RAM / 8 vCPU — $96/mo
- Or split into multiple droplets (API server + processing workers)

### Disk Space Management
- Temporary video/audio files deleted after processing
- Extracted key frames stored for 30 days, then cleaned
- Database grows slowly (~1KB per processed video metadata)

---

## OpenClaw Autonomous Management

### Daily Automated Tasks (Level 2 — No Approval Needed)

| Task | Method | Schedule |
|------|--------|----------|
| Health check | Ping all endpoints, restart if down | Every 5 minutes |
| Retry failed jobs | Re-queue any stuck/failed video jobs | Every 15 minutes |
| Clean temp files | Delete processed video/audio files older than 1 hour | Every hour |
| Clean old frames | Delete key frame images older than 30 days | Daily midnight |
| Usage stats | Pull from database, format report | Daily 8am |
| Revenue stats | Pull from Stripe API | Daily 8am |
| Send daily report | Email via SendGrid to your inbox | Daily 8am |
| Error log review | Scan logs, categorize errors | Daily 9am |

### Daily Report Email Format
```
Subject: VideoMind Daily Report — Feb 6, 2026

NEW USERS: 3 (Total: 127)
REVENUE TODAY: $48.00 (MRR: $1,430)
VIDEOS PROCESSED: 89 (Success: 87, Failed: 2)
SERVER: CPU 34% | RAM 62% | Disk 41%
ERRORS: 2 (1x timeout on long video, 1x invalid URL)
ACTION NEEDED: None

---
Status: All systems operational
```

### Weekly Tasks (Level 1 — Your Approval Needed)

| Task | What OpenClaw Does | You Do |
|------|-------------------|--------|
| Support tickets | Drafts replies to user emails | Review and approve |
| Prompt improvements | Tests better summary/chapter prompts, shows comparison | Pick the better one |
| Feature additions | You request, OpenClaw codes and tests | Review the code |
| Marketing drafts | Writes tweets/posts about product | Approve before posting |
| Pricing adjustments | Analyzes usage patterns, suggests changes | Decide yes/no |

### Self-Healing System

```python
# Runs every 5 minutes as a cron job
def health_check():
    # 1. Is the API alive?
    if not ping("/api/v1/health"):
        restart_fastapi_server()
        alert_owner("API was down, restarted automatically")

    # 2. Is Redis alive? (needed for job queue)
    if not ping_redis():
        restart_redis()
        alert_owner("Redis was down, restarted automatically")

    # 3. Any stuck jobs? (processing for more than 10 minutes)
    stuck_jobs = get_jobs_older_than(minutes=10, status="processing")
    for job in stuck_jobs:
        retry_job(job)

    # 4. Disk space check
    if disk_usage() > 85:
        clean_old_temp_files()
        alert_owner("Disk was at 85%, cleaned temp files")

    # 5. Memory check
    if ram_usage() > 90:
        alert_owner("RAM at 90% — may need server upgrade")
```

---

## Project File Structure

```
videomind/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py             # Environment variables, settings
│   ├── models.py             # Database models (User, Job, Result)
│   ├── database.py           # SQLite connection setup
│   │
│   ├── routers/
│   │   ├── analyze.py        # POST /analyze endpoint
│   │   ├── results.py        # GET /status, /result endpoints
│   │   ├── ask.py            # POST /ask endpoint
│   │   ├── blog.py           # POST /to-blog endpoint
│   │   ├── auth.py           # POST /register, API key management
│   │   └── usage.py          # GET /usage endpoint
│   │
│   ├── services/
│   │   ├── downloader.py     # yt-dlp video download logic
│   │   ├── audio.py          # FFmpeg audio extraction
│   │   ├── frames.py         # FFmpeg frame extraction + dedup
│   │   ├── transcriber.py    # Whisper speech-to-text
│   │   ├── vision.py         # GPT-4o Vision frame analysis
│   │   ├── summarizer.py     # GPT-4o summary/chapter generation
│   │   ├── qa.py             # Question answering over transcript
│   │   └── blog_writer.py    # Video-to-blog conversion
│   │
│   ├── workers/
│   │   └── tasks.py          # Celery background tasks
│   │
│   ├── middleware/
│   │   ├── auth.py           # API key validation
│   │   └── rate_limit.py     # Rate limiting per tier
│   │
│   └── utils/
│       ├── stripe_utils.py   # Stripe API helpers
│       ├── email_utils.py    # SendGrid email helpers
│       └── health.py         # Health check + self-healing
│
├── scripts/
│   ├── health_check.py       # Cron job for self-healing
│   ├── daily_report.py       # Cron job for daily email report
│   ├── cleanup.py            # Cron job for temp file cleanup
│   └── setup_server.sh       # One-command server setup script
│
├── data/
│   ├── videomind.db          # SQLite database
│   └── frames/               # Extracted key frames (temp storage)
│
├── requirements.txt          # Python dependencies
├── .env                      # API keys (Stripe, OpenAI, SendGrid)
├── docker-compose.yml        # Optional: containerized deployment
└── README.md                 # API documentation
```

---

## Implementation Order

### Phase 1: Core MVP (Week 1)
1. FastAPI app skeleton with health endpoint
2. Video download service (yt-dlp)
3. Audio extraction (FFmpeg)
4. Transcription (Whisper)
5. Basic summary generation (GPT-4o)
6. Job queue with Celery + Redis
7. SQLite database for jobs and results
8. API key authentication (hardcoded keys for testing)

### Phase 2: Vision + Features (Week 2)
1. Frame extraction with smart deduplication
2. GPT-4o Vision analysis of frames
3. Merged timeline (audio + visual)
4. Chapter auto-detection
5. Subtitle SRT generation
6. Q&A endpoint
7. Video-to-blog endpoint

### Phase 3: Users + Payments (Week 3)
1. User registration endpoint
2. API key generation
3. Stripe integration (subscriptions)
4. Tier-based rate limiting
5. Usage tracking endpoint
6. Stripe webhook handling

### Phase 4: Autonomy + Polish (Week 4)
1. Health check cron job (self-healing)
2. Daily report email system
3. Temp file cleanup cron
4. Error logging and monitoring
5. OpenClaw management scripts
6. Server setup automation script

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| YouTube blocks yt-dlp | Can't download videos | Support direct file uploads as fallback; yt-dlp community updates frequently |
| OpenAI API costs spike | Lower margins | Smart frame dedup; cache results; set max frames per video |
| Server overloaded | Slow/failed processing | Queue system handles backpressure; rate limits protect server |
| Whisper accuracy issues | Bad transcripts | Use "medium" model; allow users to request re-transcription |
| Users abuse free tier | High costs, no revenue | Strict rate limits; require email verification |
| Stripe account issues | Can't collect payments | Keep Stripe account in good standing; have backup payment processor |

---

## Success Metrics

| Metric | Target (Month 1) | Target (Month 3) | Target (Month 6) |
|--------|------------------|-------------------|-------------------|
| Registered users | 50 | 500 | 2,000 |
| Paying users | 5 | 50 | 200 |
| MRR (Monthly Recurring Revenue) | $60 | $600 | $3,000 |
| Videos processed/day | 20 | 200 | 1,000 |
| API uptime | 95% | 99% | 99.5% |
| Avg processing time | < 3 min | < 2 min | < 1 min |
