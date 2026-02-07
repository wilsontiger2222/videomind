import uuid
import json
import hashlib
import secrets
from app.database import get_connection

def create_job(db_path, url, options):
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    conn = get_connection(db_path)
    conn.execute(
        "INSERT INTO jobs (id, url, options) VALUES (?, ?, ?)",
        (job_id, url, json.dumps(options))
    )
    conn.commit()
    conn.close()
    return job_id

def get_job(db_path, job_id):
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)

def update_job_status(db_path, job_id, status=None, progress=None, step=None, **kwargs):
    conn = get_connection(db_path)
    updates = []
    values = []
    if status is not None:
        updates.append("status = ?")
        values.append(status)
    if progress is not None:
        updates.append("progress = ?")
        values.append(progress)
    if step is not None:
        updates.append("step = ?")
        values.append(step)
    for key, value in kwargs.items():
        updates.append(f"{key} = ?")
        values.append(value if isinstance(value, str) else json.dumps(value))
    if status == "completed" or status == "failed":
        updates.append("completed_at = CURRENT_TIMESTAMP")
    values.append(job_id)
    conn.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?", values)
    conn.commit()
    conn.close()


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
