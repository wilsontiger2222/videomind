# VideoMind API

A hosted API that lets AI agents and developers "watch" and understand any video. Send a video URL, get back a transcript, visual scene descriptions, summary, chapters, subtitles, and the ability to ask questions about the video.

## Features

- **Video Download** -- Supports YouTube and 1000+ sites via yt-dlp
- **Audio Transcription** -- OpenAI Whisper API with timestamped segments
- **Visual Analysis** -- GPT-4o Vision analyzes key frames with smart deduplication
- **Summaries & Chapters** -- Auto-generated short/detailed summaries and chapter markers
- **Q&A** -- Ask natural language questions about any processed video
- **Blog Generation** -- Convert video content into markdown blog articles
- **Subtitle Export** -- SRT subtitle generation from transcript segments
- **User Accounts** -- Registration with hashed passwords and API key generation
- **Stripe Payments** -- Subscription tiers (Free/Pro/Business) with webhook handling
- **Rate Limiting** -- Tier-based request throttling (10/100/500 requests per hour)
- **Health Monitoring** -- Stuck job detection, disk/CPU/memory checks, daily reports
- **Cron Scripts** -- Ready-to-schedule health checks, cleanup, and email reports

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Web Framework | FastAPI |
| Video Download | yt-dlp |
| Audio/Video Processing | FFmpeg |
| Transcription | OpenAI Whisper API |
| AI (summaries, vision, Q&A, blog) | OpenAI GPT-4o |
| Database | SQLite |
| Payments | Stripe |
| Email | SendGrid |
| System Monitoring | psutil |

## Quick Start

### Prerequisites

- Python 3.10+
- FFmpeg installed and on PATH ([download](https://ffmpeg.org/download.html))
- An OpenAI API key ([get one](https://platform.openai.com/api-keys))

### Install

```bash
cd videomind
pip install -r requirements.txt
```

### Configure

Create a `.env` file in the `videomind/` directory:

```env
# Required
OPENAI_API_KEY=sk-proj-your-key-here

# Payments (optional -- skip for local testing)
STRIPE_SECRET_KEY=sk_test_your-key
STRIPE_WEBHOOK_SECRET=whsec_your-key
STRIPE_PRO_PRICE_ID=price_your-pro-id
STRIPE_BUSINESS_PRICE_ID=price_your-biz-id

# Email reports (optional -- gracefully skips if empty)
SENDGRID_API_KEY=SG.your-key
ADMIN_EMAIL=you@example.com
```

### Run

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API is live at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## API Endpoints

### Public

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| POST | `/api/v1/register` | Create account, get API key |

### Authenticated (Bearer token)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/analyze` | Submit a video URL for processing |
| GET | `/api/v1/status/{job_id}` | Check processing progress |
| GET | `/api/v1/result/{job_id}` | Get full results (transcript, summary, visual analysis) |
| POST | `/api/v1/ask` | Ask a question about a processed video |
| POST | `/api/v1/to-blog` | Convert a processed video into a blog article |
| GET | `/api/v1/usage` | Check your plan, limits, and usage |
| GET | `/api/v1/admin/stats` | System health and usage statistics |

### Webhooks

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/stripe/webhook` | Stripe subscription lifecycle events |

## Usage Examples

### Register and get an API key

```bash
curl -X POST http://localhost:8000/api/v1/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepass123"}'
```

Response:
```json
{
  "user_id": "user_a1b2c3d4e5f6",
  "email": "user@example.com",
  "api_key": "sk_abc123...",
  "plan": "free"
}
```

### Submit a video

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Authorization: Bearer sk_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=example",
    "options": {
      "transcript": true,
      "visual_analysis": true,
      "summary": true
    }
  }'
```

### Check status

```bash
curl http://localhost:8000/api/v1/status/job_abc123 \
  -H "Authorization: Bearer sk_abc123..."
```

### Get results

```bash
curl http://localhost:8000/api/v1/result/job_abc123 \
  -H "Authorization: Bearer sk_abc123..."
```

### Ask a question

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Authorization: Bearer sk_abc123..." \
  -H "Content-Type: application/json" \
  -d '{"job_id": "job_abc123", "question": "What was discussed at the 5 minute mark?"}'
```

### Generate a blog post

```bash
curl -X POST http://localhost:8000/api/v1/to-blog \
  -H "Authorization: Bearer sk_abc123..." \
  -H "Content-Type: application/json" \
  -d '{"job_id": "job_abc123", "style": "tutorial"}'
```

## Pricing Tiers

| Feature | Free | Pro ($12/mo) | Business ($39/mo) |
|---------|------|-------------|-------------------|
| Videos per day | 3 | 30 | 150 |
| API rate limit | 10/hour | 100/hour | 500/hour |
| Transcript + Summary | Yes | Yes | Yes |
| Visual analysis | No | Yes | Yes |
| Q&A | No | Yes | Yes |
| Blog generation | No | No | Yes |

## Project Structure

```
videomind/
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Environment variables
│   ├── database.py              # SQLite setup (jobs + users tables)
│   ├── models.py                # CRUD functions (jobs, users, usage)
│   ├── logging_config.py        # Structured logging setup
│   ├── routers/
│   │   ├── analyze.py           # POST /analyze
│   │   ├── results.py           # GET /status, /result
│   │   ├── ask.py               # POST /ask
│   │   ├── blog.py              # POST /to-blog
│   │   ├── auth.py              # POST /register
│   │   ├── usage.py             # GET /usage
│   │   ├── admin.py             # GET /admin/stats
│   │   └── stripe_webhook.py    # POST /stripe/webhook
│   ├── services/
│   │   ├── downloader.py        # yt-dlp video download
│   │   ├── audio.py             # FFmpeg audio extraction
│   │   ├── frames.py            # FFmpeg frame extraction + dedup
│   │   ├── transcriber.py       # OpenAI Whisper transcription
│   │   ├── vision.py            # GPT-4o Vision frame analysis
│   │   ├── summarizer.py        # GPT-4o summary + chapters
│   │   ├── qa.py                # GPT-4o Q&A over video
│   │   ├── blog_writer.py       # GPT-4o blog generation
│   │   ├── stripe_utils.py      # Stripe customer + checkout
│   │   ├── email_utils.py       # SendGrid email wrapper
│   │   ├── health.py            # System health checks
│   │   ├── cleanup.py           # Temp file cleanup
│   │   └── report.py            # Daily stats report
│   ├── middleware/
│   │   ├── auth.py              # API key auth (DB + legacy)
│   │   └── rate_limit.py        # Tier-based rate limiting
│   └── workers/
│       └── pipeline.py          # Video processing pipeline
├── scripts/
│   ├── health_check.py          # Cron: health + stuck job recovery
│   ├── cleanup.py               # Cron: delete old temp/frame files
│   └── daily_report.py          # Cron: generate + email daily stats
├── tests/                       # 106 tests across all features
├── requirements.txt
└── .env                         # API keys (not committed)
```

## Cron Jobs

For production, schedule these in crontab:

```cron
# Health check every 5 minutes
*/5 * * * * cd /path/to/videomind && python scripts/health_check.py

# Cleanup temp files every hour
0 * * * * cd /path/to/videomind && python scripts/cleanup.py

# Daily report at 8am
0 8 * * * cd /path/to/videomind && python scripts/daily_report.py
```

## Tests

```bash
python -m pytest tests/ -v
```

106 tests covering all features across 4 phases. All tests use mocked external services (no real API calls needed to run tests).

## Deployment

### DigitalOcean (Recommended)

**Starting setup** ($24/mo — 4GB RAM / 2 vCPU):

```bash
# On the server
sudo apt update && sudo apt install -y python3 python3-pip ffmpeg
git clone https://github.com/wilsontiger2222/videomind.git
cd videomind
pip install -r requirements.txt

# Create .env with your API keys
nano .env

# Run
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For production, put **nginx** in front for HTTPS and use **systemd** to keep the process running.

### Stripe Webhook Setup

1. In Stripe Dashboard, create a webhook endpoint: `https://yourdomain.com/api/v1/stripe/webhook`
2. Subscribe to events: `checkout.session.completed`, `customer.subscription.deleted`
3. Copy the webhook signing secret to your `.env` as `STRIPE_WEBHOOK_SECRET`

## License

MIT
