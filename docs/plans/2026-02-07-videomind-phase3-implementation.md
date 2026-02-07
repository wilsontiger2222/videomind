# VideoMind API — Phase 3 Implementation Plan (Users + Payments)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add user registration, database-backed API keys, Stripe subscriptions, tier-based rate limiting, and usage tracking to the VideoMind API.

**Architecture:** Users table stores email, password hash (PBKDF2), API key, plan tier, and Stripe customer ID. Auth middleware switches from env-based to DB-backed key lookup, attaching the user to each request. Rate limiting middleware checks requests-per-hour by tier. Jobs get a user_id column. Stripe handles subscription lifecycle via webhooks.

**Tech Stack:** Python 3.14, FastAPI, SQLite, hashlib (PBKDF2 password hashing), secrets (API key generation), stripe (payments)

**Pricing tiers from design doc:**
- Free: 3 videos/day, 10 req/hour, no vision/Q&A/blog
- Pro ($12/mo): 30 videos/day, 100 req/hour, vision + Q&A
- Business ($39/mo): 150 videos/day, 500 req/hour, all features

---

### Task 1: Add Dependencies for Phase 3

**Files:**
- Modify: `videomind/requirements.txt`

**Step 1: Update requirements.txt**

Add this line to the end of `videomind/requirements.txt`:

```
stripe
```

**Step 2: Install new dependency**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pip install stripe`
Expected: Successful install

**Step 3: Verify import works**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -c "import stripe; print(f'stripe={stripe.VERSION}')"`
Expected: prints version

**Step 4: Update requirements.txt with installed version**

Update the `stripe` line to include the version that was installed (e.g., `stripe==11.x.x`).

**Step 5: Add STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET to config.py**

In `videomind/app/config.py`, add after the existing config lines:

```python
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRO_PRICE_ID = os.getenv("STRIPE_PRO_PRICE_ID", "price_pro_placeholder")
STRIPE_BUSINESS_PRICE_ID = os.getenv("STRIPE_BUSINESS_PRICE_ID", "price_biz_placeholder")
```

**Step 6: Run existing tests to confirm nothing broke**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL 43 PASS

**Step 7: Commit**

```bash
git add requirements.txt app/config.py
git commit -m "chore: add stripe dependency and config for Phase 3"
```

---

### Task 2: Users Table and User Model Functions

**Files:**
- Modify: `videomind/app/database.py` — add users table
- Modify: `videomind/app/models.py` — add user CRUD functions
- Create: `videomind/tests/test_users.py`

**Step 1: Write the failing test**

```python
# tests/test_users.py
import os
import pytest
from app.database import init_db
from app.models import create_user, get_user_by_email, get_user_by_api_key, update_user_plan

TEST_DB = "./data/test_users.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_create_user_returns_api_key():
    result = create_user(TEST_DB, email="test@example.com", password="securepass123")
    assert "api_key" in result
    assert result["api_key"].startswith("sk_")
    assert result["email"] == "test@example.com"
    assert result["plan"] == "free"


def test_create_user_duplicate_email_fails():
    create_user(TEST_DB, email="test@example.com", password="pass1")
    with pytest.raises(ValueError, match="Email already registered"):
        create_user(TEST_DB, email="test@example.com", password="pass2")


def test_get_user_by_email():
    create_user(TEST_DB, email="find@example.com", password="pass")
    user = get_user_by_email(TEST_DB, "find@example.com")
    assert user is not None
    assert user["email"] == "find@example.com"


def test_get_user_by_email_not_found():
    user = get_user_by_email(TEST_DB, "nobody@example.com")
    assert user is None


def test_get_user_by_api_key():
    result = create_user(TEST_DB, email="key@example.com", password="pass")
    user = get_user_by_api_key(TEST_DB, result["api_key"])
    assert user is not None
    assert user["email"] == "key@example.com"


def test_get_user_by_api_key_not_found():
    user = get_user_by_api_key(TEST_DB, "sk_nonexistent")
    assert user is None


def test_update_user_plan():
    result = create_user(TEST_DB, email="plan@example.com", password="pass")
    update_user_plan(TEST_DB, result["api_key"], plan="pro", stripe_customer_id="cus_123")
    user = get_user_by_api_key(TEST_DB, result["api_key"])
    assert user["plan"] == "pro"
    assert user["stripe_customer_id"] == "cus_123"


def test_password_is_hashed():
    result = create_user(TEST_DB, email="hash@example.com", password="mypassword")
    user = get_user_by_email(TEST_DB, "hash@example.com")
    assert user["password_hash"] != "mypassword"
    assert len(user["password_hash"]) > 20
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_users.py -v`
Expected: FAIL — functions don't exist

**Step 3: Add users table to database.py**

In `videomind/app/database.py`, add a second CREATE TABLE statement inside `init_db()`, after the jobs table commit and before `conn.close()`:

```python
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            api_key TEXT UNIQUE NOT NULL,
            plan TEXT DEFAULT 'free',
            stripe_customer_id TEXT DEFAULT '',
            videos_today INTEGER DEFAULT 0,
            videos_today_reset TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
```

**Step 4: Add user CRUD functions to models.py**

Add these functions to the end of `videomind/app/models.py`:

```python
import hashlib
import secrets


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hash_value = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return f"{salt}:{hash_value.hex()}"


def _verify_password(password: str, password_hash: str) -> bool:
    salt, hash_hex = password_hash.split(":")
    expected = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return expected.hex() == hash_hex


def create_user(db_path, email, password):
    conn = get_connection(db_path)
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        raise ValueError("Email already registered")

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    api_key = f"sk_{secrets.token_hex(24)}"
    password_hash = _hash_password(password)

    conn.execute(
        "INSERT INTO users (id, email, password_hash, api_key) VALUES (?, ?, ?, ?)",
        (user_id, email, password_hash, api_key)
    )
    conn.commit()
    conn.close()

    return {"user_id": user_id, "email": email, "api_key": api_key, "plan": "free"}


def get_user_by_email(db_path, email):
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def get_user_by_api_key(db_path, api_key):
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM users WHERE api_key = ?", (api_key,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def update_user_plan(db_path, api_key, plan=None, stripe_customer_id=None):
    conn = get_connection(db_path)
    updates = []
    values = []
    if plan is not None:
        updates.append("plan = ?")
        values.append(plan)
    if stripe_customer_id is not None:
        updates.append("stripe_customer_id = ?")
        values.append(stripe_customer_id)
    values.append(api_key)
    conn.execute(f"UPDATE users SET {', '.join(updates)} WHERE api_key = ?", values)
    conn.commit()
    conn.close()
```

**Step 5: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_users.py -v`
Expected: ALL PASS

**Step 6: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add app/database.py app/models.py tests/test_users.py
git commit -m "feat: users table with registration, API key generation, and plan management"
```

---

### Task 3: Registration Endpoint

**Files:**
- Create: `videomind/app/routers/auth.py`
- Create: `videomind/tests/test_register.py`
- Modify: `videomind/app/main.py` — add auth router
- Modify: `videomind/app/middleware/auth.py` — add /api/v1/register to PUBLIC_PATHS

**Step 1: Write the failing test**

```python
# tests/test_register.py
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

TEST_DB = "./data/test_register.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


def test_register_returns_api_key():
    with patch("app.routers.auth.DATABASE_URL", TEST_DB):
        response = client.post(
            "/api/v1/register",
            json={"email": "new@example.com", "password": "securepass123"}
        )
    assert response.status_code == 200
    data = response.json()
    assert "api_key" in data
    assert data["api_key"].startswith("sk_")
    assert data["email"] == "new@example.com"
    assert data["plan"] == "free"


def test_register_duplicate_email():
    with patch("app.routers.auth.DATABASE_URL", TEST_DB):
        client.post("/api/v1/register", json={"email": "dup@example.com", "password": "pass1"})
        response = client.post("/api/v1/register", json={"email": "dup@example.com", "password": "pass2"})
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_register_missing_fields():
    response = client.post("/api/v1/register", json={"email": "no@pass.com"})
    assert response.status_code == 422


def test_register_short_password():
    with patch("app.routers.auth.DATABASE_URL", TEST_DB):
        response = client.post(
            "/api/v1/register",
            json={"email": "short@example.com", "password": "12345"}
        )
    assert response.status_code == 400
    assert "at least 8 characters" in response.json()["detail"]
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_register.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write auth.py router**

```python
# app/routers/auth.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
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
```

**Step 4: Update main.py to include auth router**

In `videomind/app/main.py`:
- Change import to: `from app.routers import analyze, results, ask, blog, auth`
- Add after blog router: `app.include_router(auth.router)`

**Step 5: Add /api/v1/register to PUBLIC_PATHS in middleware/auth.py**

In `videomind/app/middleware/auth.py`, add `"/api/v1/register"` to the PUBLIC_PATHS list.

**Step 6: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_register.py -v`
Expected: PASS

**Step 7: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 8: Commit**

```bash
git add app/routers/auth.py tests/test_register.py app/main.py app/middleware/auth.py
git commit -m "feat: POST /api/v1/register endpoint for user registration"
```

---

### Task 4: Update Auth Middleware to Use DB-Backed API Keys

**Files:**
- Modify: `videomind/app/middleware/auth.py` — look up keys from DB, attach user to request
- Modify: `videomind/tests/test_auth.py` — update tests for DB-backed auth
- Modify: `videomind/app/config.py` — keep API_KEYS as fallback for backwards compat

**Step 1: Write the failing test**

Replace the contents of `videomind/tests/test_auth.py`:

```python
# tests/test_auth.py
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.models import create_user

TEST_DB = "./data/test_auth2.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


def test_request_without_api_key_is_rejected():
    response = client.post("/api/v1/analyze", json={"url": "https://youtube.com/watch?v=test"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing API key"


def test_request_with_invalid_api_key_is_rejected():
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        response = client.post(
            "/api/v1/analyze",
            json={"url": "https://youtube.com/watch?v=test"},
            headers={"Authorization": "Bearer sk_invalid_key"}
        )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


def test_request_with_valid_db_api_key_passes():
    result = create_user(TEST_DB, email="auth@example.com", password="securepass123")
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        response = client.get(
            "/api/v1/health",
            headers={"Authorization": f"Bearer {result['api_key']}"}
        )
    assert response.status_code == 200


def test_request_with_legacy_env_api_key_passes():
    response = client.get(
        "/api/v1/health",
        headers={"Authorization": "Bearer test-key-123"}
    )
    assert response.status_code == 200


def test_health_endpoint_works_without_key():
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_register_works_without_key():
    with patch("app.routers.auth.DATABASE_URL", TEST_DB):
        response = client.post(
            "/api/v1/register",
            json={"email": "nokey@example.com", "password": "securepass123"}
        )
    assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_auth.py -v`
Expected: FAIL — DB-backed lookup not implemented

**Step 3: Update auth middleware**

Replace `videomind/app/middleware/auth.py`:

```python
# app/middleware/auth.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import API_KEYS, DATABASE_URL
from app.models import get_user_by_api_key

PUBLIC_PATHS = ["/api/v1/health", "/api/v1/register", "/api/v1/stripe/webhook", "/docs", "/openapi.json", "/redoc"]


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

        # Check legacy env-based keys first (backwards compat for testing)
        if api_key in API_KEYS:
            request.state.user = {"plan": "business", "api_key": api_key, "id": "legacy"}
            return await call_next(request)

        # Check database-backed keys
        user = get_user_by_api_key(DATABASE_URL, api_key)
        if user is None:
            return JSONResponse(
                status_code=401, content={"detail": "Invalid API key"}
            )

        request.state.user = user
        return await call_next(request)
```

**Step 4: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_auth.py -v`
Expected: ALL PASS

**Step 5: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS (legacy test-key-123 still works for all existing tests)

**Step 6: Commit**

```bash
git add app/middleware/auth.py tests/test_auth.py
git commit -m "feat: DB-backed API key authentication with legacy key fallback"
```

---

### Task 5: Add user_id to Jobs and Track Usage

**Files:**
- Modify: `videomind/app/database.py` — add user_id column to jobs
- Modify: `videomind/app/models.py` — add usage tracking functions
- Create: `videomind/tests/test_usage.py`

**Step 1: Write the failing test**

```python
# tests/test_usage.py
import os
import pytest
from app.database import init_db
from app.models import (
    create_user, create_job, get_user_usage,
    increment_user_video_count, reset_daily_video_count
)

TEST_DB = "./data/test_usage.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


def test_get_user_usage_new_user():
    result = create_user(TEST_DB, email="usage@example.com", password="securepass123")
    usage = get_user_usage(TEST_DB, result["api_key"])
    assert usage["plan"] == "free"
    assert usage["videos_today"] == 0
    assert usage["videos_limit"] == 3
    assert usage["requests_limit"] == 10


def test_increment_video_count():
    result = create_user(TEST_DB, email="inc@example.com", password="securepass123")
    increment_user_video_count(TEST_DB, result["api_key"])
    increment_user_video_count(TEST_DB, result["api_key"])
    usage = get_user_usage(TEST_DB, result["api_key"])
    assert usage["videos_today"] == 2


def test_reset_daily_video_count():
    result = create_user(TEST_DB, email="reset@example.com", password="securepass123")
    increment_user_video_count(TEST_DB, result["api_key"])
    reset_daily_video_count(TEST_DB, result["api_key"])
    usage = get_user_usage(TEST_DB, result["api_key"])
    assert usage["videos_today"] == 0


def test_usage_limits_by_plan():
    result = create_user(TEST_DB, email="pro@example.com", password="securepass123")
    from app.models import update_user_plan
    update_user_plan(TEST_DB, result["api_key"], plan="pro")
    usage = get_user_usage(TEST_DB, result["api_key"])
    assert usage["videos_limit"] == 30
    assert usage["requests_limit"] == 100


def test_usage_limits_business():
    result = create_user(TEST_DB, email="biz@example.com", password="securepass123")
    from app.models import update_user_plan
    update_user_plan(TEST_DB, result["api_key"], plan="business")
    usage = get_user_usage(TEST_DB, result["api_key"])
    assert usage["videos_limit"] == 150
    assert usage["requests_limit"] == 500
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_usage.py -v`
Expected: FAIL — functions don't exist

**Step 3: Add user_id column to jobs table in database.py**

In `videomind/app/database.py`, add `user_id TEXT DEFAULT '',` to the jobs CREATE TABLE, after the `id` column line.

**Step 4: Add usage functions to models.py**

Add these functions and the PLAN_LIMITS dict to `videomind/app/models.py`:

```python
PLAN_LIMITS = {
    "free": {"videos_per_day": 3, "requests_per_hour": 10},
    "pro": {"videos_per_day": 30, "requests_per_hour": 100},
    "business": {"videos_per_day": 150, "requests_per_hour": 500},
}


def get_user_usage(db_path, api_key):
    user = get_user_by_api_key(db_path, api_key)
    if user is None:
        return None
    plan = user["plan"]
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    return {
        "plan": plan,
        "videos_today": user["videos_today"],
        "videos_limit": limits["videos_per_day"],
        "requests_limit": limits["requests_per_hour"],
    }


def increment_user_video_count(db_path, api_key):
    conn = get_connection(db_path)
    conn.execute("UPDATE users SET videos_today = videos_today + 1 WHERE api_key = ?", (api_key,))
    conn.commit()
    conn.close()


def reset_daily_video_count(db_path, api_key):
    conn = get_connection(db_path)
    conn.execute("UPDATE users SET videos_today = 0 WHERE api_key = ?", (api_key,))
    conn.commit()
    conn.close()
```

**Step 5: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_usage.py -v`
Expected: ALL PASS

**Step 6: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add app/database.py app/models.py tests/test_usage.py
git commit -m "feat: usage tracking with plan-based limits and daily video counts"
```

---

### Task 6: Rate Limiting Middleware

**Files:**
- Create: `videomind/app/middleware/rate_limit.py`
- Create: `videomind/tests/test_rate_limit.py`
- Modify: `videomind/app/main.py` — add rate limit middleware

**Step 1: Write the failing test**

```python
# tests/test_rate_limit.py
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.models import create_user

TEST_DB = "./data/test_rate_limit.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


def test_rate_limit_allows_normal_requests():
    result = create_user(TEST_DB, email="normal@example.com", password="securepass123")
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        response = client.get(
            "/api/v1/health",
            headers={"Authorization": f"Bearer {result['api_key']}"}
        )
    assert response.status_code == 200


def test_rate_limit_blocks_after_exceeding_limit():
    result = create_user(TEST_DB, email="limited@example.com", password="securepass123")
    # Free plan = 10 requests/hour. Send 11 requests.
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        with patch("app.middleware.rate_limit.DATABASE_URL", TEST_DB):
            for i in range(10):
                response = client.get(
                    "/api/v1/health",
                    headers={"Authorization": f"Bearer {result['api_key']}"}
                )
                assert response.status_code == 200

            response = client.get(
                "/api/v1/health",
                headers={"Authorization": f"Bearer {result['api_key']}"}
            )
            assert response.status_code == 429
            assert "Rate limit exceeded" in response.json()["detail"]


def test_rate_limit_skips_public_paths():
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_rate_limit_skips_legacy_keys():
    # Legacy keys get business-tier limits (500/hr), so they shouldn't be rate limited easily
    for i in range(15):
        response = client.get(
            "/api/v1/health",
            headers={"Authorization": "Bearer test-key-123"}
        )
        assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_rate_limit.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write rate_limit.py**

```python
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

PUBLIC_PATHS = ["/api/v1/health", "/api/v1/register", "/api/v1/stripe/webhook", "/docs", "/openapi.json", "/redoc"]


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
```

**Step 4: Update main.py to add rate limit middleware**

In `videomind/app/main.py`:
- Add import: `from app.middleware.rate_limit import RateLimitMiddleware`
- Add BEFORE the APIKeyMiddleware line: `app.add_middleware(RateLimitMiddleware)`

Note: Starlette processes middleware in reverse order of `add_middleware` calls, so RateLimitMiddleware added first means it runs AFTER APIKeyMiddleware (which is what we want — auth first, then rate limit).

**Step 5: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_rate_limit.py -v`
Expected: PASS

**Step 6: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add app/middleware/rate_limit.py tests/test_rate_limit.py app/main.py
git commit -m "feat: tier-based rate limiting middleware"
```

---

### Task 7: Usage Tracking Endpoint

**Files:**
- Create: `videomind/app/routers/usage.py`
- Create: `videomind/tests/test_usage_endpoint.py`
- Modify: `videomind/app/main.py` — add usage router

**Step 1: Write the failing test**

```python
# tests/test_usage_endpoint.py
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.models import create_user, increment_user_video_count

TEST_DB = "./data/test_usage_endpoint.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


def test_usage_returns_plan_info():
    result = create_user(TEST_DB, email="usage@example.com", password="securepass123")
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        with patch("app.routers.usage.DATABASE_URL", TEST_DB):
            response = client.get(
                "/api/v1/usage",
                headers={"Authorization": f"Bearer {result['api_key']}"}
            )
    assert response.status_code == 200
    data = response.json()
    assert data["plan"] == "free"
    assert data["videos_today"] == 0
    assert data["videos_limit"] == 3
    assert data["requests_limit"] == 10


def test_usage_reflects_video_count():
    result = create_user(TEST_DB, email="count@example.com", password="securepass123")
    increment_user_video_count(TEST_DB, result["api_key"])
    increment_user_video_count(TEST_DB, result["api_key"])
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        with patch("app.routers.usage.DATABASE_URL", TEST_DB):
            response = client.get(
                "/api/v1/usage",
                headers={"Authorization": f"Bearer {result['api_key']}"}
            )
    assert response.status_code == 200
    assert response.json()["videos_today"] == 2


def test_usage_with_legacy_key():
    response = client.get(
        "/api/v1/usage",
        headers={"Authorization": "Bearer test-key-123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["plan"] == "business"
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_usage_endpoint.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write usage.py router**

```python
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
```

**Step 4: Update main.py**

In `videomind/app/main.py`:
- Change import to: `from app.routers import analyze, results, ask, blog, auth, usage`
- Add: `app.include_router(usage.router)`

**Step 5: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_usage_endpoint.py -v`
Expected: PASS

**Step 6: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add app/routers/usage.py tests/test_usage_endpoint.py app/main.py
git commit -m "feat: GET /api/v1/usage endpoint for usage tracking"
```

---

### Task 8: Stripe Utils

**Files:**
- Create: `videomind/app/services/stripe_utils.py`
- Create: `videomind/tests/test_stripe_utils.py`

**Step 1: Write the failing test**

```python
# tests/test_stripe_utils.py
import pytest
from unittest.mock import patch, MagicMock
from app.services.stripe_utils import create_stripe_customer, create_checkout_session


@patch("app.services.stripe_utils.stripe.Customer.create")
def test_create_stripe_customer(mock_create):
    mock_create.return_value = MagicMock(id="cus_test123")

    customer_id = create_stripe_customer("user@example.com")

    assert customer_id == "cus_test123"
    mock_create.assert_called_once_with(email="user@example.com")


@patch("app.services.stripe_utils.stripe.checkout.Session.create")
def test_create_checkout_session_pro(mock_create):
    mock_create.return_value = MagicMock(url="https://checkout.stripe.com/session123")

    url = create_checkout_session("cus_test123", "pro")

    assert url == "https://checkout.stripe.com/session123"
    mock_create.assert_called_once()
    call_kwargs = mock_create.call_args[1]
    assert call_kwargs["customer"] == "cus_test123"
    assert call_kwargs["mode"] == "subscription"


@patch("app.services.stripe_utils.stripe.checkout.Session.create")
def test_create_checkout_session_business(mock_create):
    mock_create.return_value = MagicMock(url="https://checkout.stripe.com/biz456")

    url = create_checkout_session("cus_test123", "business")

    assert url == "https://checkout.stripe.com/biz456"


def test_create_checkout_session_invalid_plan():
    with pytest.raises(ValueError, match="Invalid plan"):
        create_checkout_session("cus_test123", "enterprise")
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_stripe_utils.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write stripe_utils.py**

```python
# app/services/stripe_utils.py
import stripe
from app.config import STRIPE_SECRET_KEY, STRIPE_PRO_PRICE_ID, STRIPE_BUSINESS_PRICE_ID

stripe.api_key = STRIPE_SECRET_KEY

PRICE_IDS = {
    "pro": STRIPE_PRO_PRICE_ID,
    "business": STRIPE_BUSINESS_PRICE_ID,
}


def create_stripe_customer(email: str) -> str:
    """Create a Stripe customer and return the customer ID."""
    customer = stripe.Customer.create(email=email)
    return customer.id


def create_checkout_session(customer_id: str, plan: str) -> str:
    """Create a Stripe Checkout session for a subscription and return the URL."""
    if plan not in PRICE_IDS:
        raise ValueError(f"Invalid plan: {plan}. Must be 'pro' or 'business'.")

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": PRICE_IDS[plan], "quantity": 1}],
        mode="subscription",
        success_url="https://videomind.ai/success?session_id={CHECKOUT_SESSION_ID}",
        cancel_url="https://videomind.ai/cancel",
    )

    return session.url
```

**Step 4: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_stripe_utils.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/stripe_utils.py tests/test_stripe_utils.py
git commit -m "feat: Stripe utils for customer creation and checkout sessions"
```

---

### Task 9: Stripe Webhook Handler

**Files:**
- Create: `videomind/app/routers/stripe_webhook.py`
- Create: `videomind/tests/test_stripe_webhook.py`
- Modify: `videomind/app/main.py` — add stripe webhook router

**Step 1: Write the failing test**

```python
# tests/test_stripe_webhook.py
import os
import json
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.models import create_user, get_user_by_email, update_user_plan

TEST_DB = "./data/test_stripe_webhook.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


@patch("app.routers.stripe_webhook.stripe.Webhook.construct_event")
@patch("app.routers.stripe_webhook.DATABASE_URL", TEST_DB)
def test_webhook_checkout_completed_upgrades_user(mock_construct):
    # Create a user first
    result = create_user(TEST_DB, email="stripe@example.com", password="securepass123")
    update_user_plan(TEST_DB, result["api_key"], stripe_customer_id="cus_test123")

    mock_construct.return_value = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "customer": "cus_test123",
                "metadata": {"plan": "pro"}
            }
        }
    }

    response = client.post(
        "/api/v1/stripe/webhook",
        content=b'{"test": "data"}',
        headers={"stripe-signature": "test_sig"}
    )
    assert response.status_code == 200

    user = get_user_by_email(TEST_DB, "stripe@example.com")
    assert user["plan"] == "pro"


@patch("app.routers.stripe_webhook.stripe.Webhook.construct_event")
@patch("app.routers.stripe_webhook.DATABASE_URL", TEST_DB)
def test_webhook_subscription_deleted_downgrades_user(mock_construct):
    result = create_user(TEST_DB, email="cancel@example.com", password="securepass123")
    update_user_plan(TEST_DB, result["api_key"], plan="pro", stripe_customer_id="cus_cancel")

    mock_construct.return_value = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "customer": "cus_cancel"
            }
        }
    }

    response = client.post(
        "/api/v1/stripe/webhook",
        content=b'{"test": "data"}',
        headers={"stripe-signature": "test_sig"}
    )
    assert response.status_code == 200

    user = get_user_by_email(TEST_DB, "cancel@example.com")
    assert user["plan"] == "free"


@patch("app.routers.stripe_webhook.stripe.Webhook.construct_event")
def test_webhook_unhandled_event():
    mock_construct.return_value = {
        "type": "some.other.event",
        "data": {"object": {}}
    }

    response = client.post(
        "/api/v1/stripe/webhook",
        content=b'{"test": "data"}',
        headers={"stripe-signature": "test_sig"}
    )
    assert response.status_code == 200


@patch("app.routers.stripe_webhook.stripe.Webhook.construct_event")
def test_webhook_invalid_signature(mock_construct):
    mock_construct.side_effect = Exception("Invalid signature")

    response = client.post(
        "/api/v1/stripe/webhook",
        content=b'{"test": "data"}',
        headers={"stripe-signature": "bad_sig"}
    )
    assert response.status_code == 400
```

**Step 2: Run test to verify it fails**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_stripe_webhook.py -v`
Expected: FAIL — module doesn't exist

**Step 3: Write stripe_webhook.py**

```python
# app/routers/stripe_webhook.py
import stripe
from fastapi import APIRouter, Request, HTTPException
from app.config import STRIPE_WEBHOOK_SECRET, DATABASE_URL
from app.database import get_connection

router = APIRouter()


def _get_user_by_stripe_customer(db_path, customer_id):
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM users WHERE stripe_customer_id = ?", (customer_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def _update_plan_by_customer_id(db_path, customer_id, plan):
    conn = get_connection(db_path)
    conn.execute("UPDATE users SET plan = ? WHERE stripe_customer_id = ?", (plan, customer_id))
    conn.commit()
    conn.close()


@router.post("/api/v1/stripe/webhook")
async def stripe_webhook(request: Request):
    body = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(body, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")

    event_type = event["type"]
    data_object = event["data"]["object"]

    if event_type == "checkout.session.completed":
        customer_id = data_object.get("customer")
        plan = data_object.get("metadata", {}).get("plan", "pro")
        if customer_id:
            _update_plan_by_customer_id(DATABASE_URL, customer_id, plan)

    elif event_type == "customer.subscription.deleted":
        customer_id = data_object.get("customer")
        if customer_id:
            _update_plan_by_customer_id(DATABASE_URL, customer_id, "free")

    return {"status": "ok"}
```

**Step 4: Update main.py**

In `videomind/app/main.py`:
- Add to imports: `from app.routers import analyze, results, ask, blog, auth, usage, stripe_webhook`
- Add: `app.include_router(stripe_webhook.router)`

**Step 5: Run test to verify it passes**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_stripe_webhook.py -v`
Expected: PASS

**Step 6: Run all tests**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add app/routers/stripe_webhook.py tests/test_stripe_webhook.py app/main.py
git commit -m "feat: Stripe webhook handler for subscription lifecycle events"
```

---

### Task 10: Phase 3 End-to-End Test

**Files:**
- Create: `videomind/tests/test_e2e_phase3.py`

**Step 1: Write e2e test**

```python
# tests/test_e2e_phase3.py
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db

TEST_DB = "./data/test_e2e_phase3.db"

@pytest.fixture(autouse=True)
def setup_teardown():
    os.makedirs("./data", exist_ok=True)
    init_db(TEST_DB)
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

client = TestClient(app)


def test_full_phase3_user_lifecycle():
    """Test: register -> use API -> check usage -> upgrade via Stripe -> higher limits"""

    # Step 1: Register a new user
    with patch("app.routers.auth.DATABASE_URL", TEST_DB):
        response = client.post(
            "/api/v1/register",
            json={"email": "lifecycle@example.com", "password": "securepass123"}
        )
    assert response.status_code == 200
    api_key = response.json()["api_key"]
    assert api_key.startswith("sk_")

    # Step 2: Check initial usage (free plan)
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        with patch("app.routers.usage.DATABASE_URL", TEST_DB):
            response = client.get(
                "/api/v1/usage",
                headers={"Authorization": f"Bearer {api_key}"}
            )
    assert response.status_code == 200
    assert response.json()["plan"] == "free"
    assert response.json()["videos_limit"] == 3

    # Step 3: Simulate Stripe upgrade to pro via webhook
    from app.models import update_user_plan, get_user_by_api_key
    user = get_user_by_api_key(TEST_DB, api_key)
    update_user_plan(TEST_DB, api_key, stripe_customer_id="cus_lifecycle")

    with patch("app.routers.stripe_webhook.stripe.Webhook.construct_event") as mock_construct:
        with patch("app.routers.stripe_webhook.DATABASE_URL", TEST_DB):
            mock_construct.return_value = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "customer": "cus_lifecycle",
                        "metadata": {"plan": "pro"}
                    }
                }
            }
            response = client.post(
                "/api/v1/stripe/webhook",
                content=b'{}',
                headers={"stripe-signature": "test_sig"}
            )
    assert response.status_code == 200

    # Step 4: Check usage after upgrade (pro plan)
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        with patch("app.routers.usage.DATABASE_URL", TEST_DB):
            response = client.get(
                "/api/v1/usage",
                headers={"Authorization": f"Bearer {api_key}"}
            )
    assert response.status_code == 200
    assert response.json()["plan"] == "pro"
    assert response.json()["videos_limit"] == 30
    assert response.json()["requests_limit"] == 100

    # Step 5: Simulate subscription cancellation
    with patch("app.routers.stripe_webhook.stripe.Webhook.construct_event") as mock_construct:
        with patch("app.routers.stripe_webhook.DATABASE_URL", TEST_DB):
            mock_construct.return_value = {
                "type": "customer.subscription.deleted",
                "data": {"object": {"customer": "cus_lifecycle"}}
            }
            response = client.post(
                "/api/v1/stripe/webhook",
                content=b'{}',
                headers={"stripe-signature": "test_sig"}
            )
    assert response.status_code == 200

    # Step 6: Confirm downgrade back to free
    with patch("app.middleware.auth.DATABASE_URL", TEST_DB):
        with patch("app.routers.usage.DATABASE_URL", TEST_DB):
            response = client.get(
                "/api/v1/usage",
                headers={"Authorization": f"Bearer {api_key}"}
            )
    assert response.status_code == 200
    assert response.json()["plan"] == "free"
    assert response.json()["videos_limit"] == 3
```

**Step 2: Run e2e test**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/test_e2e_phase3.py -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `cd "C:/Users/admin/Desktop/Python/Opus4.6/videomind" && python -m pytest tests/ -v --tb=short`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add tests/test_e2e_phase3.py
git commit -m "test: end-to-end test for Phase 3 user lifecycle with Stripe"
```

---

### Phase 3 Complete Checklist

After all tasks are done, verify:

- [ ] `python -m pytest tests/ -v` — all tests pass (Phase 1 + 2 + 3)
- [ ] `POST /api/v1/register` — creates user, returns API key
- [ ] Auth works with DB-backed keys and legacy env keys
- [ ] `GET /api/v1/usage` — returns plan, limits, video count
- [ ] Rate limiting enforced per tier
- [ ] Stripe webhook upgrades/downgrades users
- [ ] All existing Phase 1 + Phase 2 tests still pass

### What's Next (Phase 4)

Phase 4 adds:
1. Health check cron job (self-healing)
2. Daily report email system
3. Temp file cleanup cron
4. Error logging and monitoring
5. Server setup automation script
