import sqlite3
import os
from app.config import DATABASE_URL

def get_connection(db_path=None):
    path = db_path or DATABASE_URL
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path=None):
    path = db_path or DATABASE_URL
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    conn = get_connection(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            user_id TEXT DEFAULT '',
            url TEXT NOT NULL,
            options TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            step TEXT DEFAULT '',
            video_title TEXT DEFAULT '',
            video_duration TEXT DEFAULT '',
            video_source TEXT DEFAULT '',
            transcript_text TEXT DEFAULT '',
            transcript_segments TEXT DEFAULT '[]',
            summary_short TEXT DEFAULT '',
            summary_detailed TEXT DEFAULT '',
            chapters TEXT DEFAULT '[]',
            subtitles_srt TEXT DEFAULT '',
            visual_analysis TEXT DEFAULT '[]',
            error_message TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)
    conn.commit()
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
    conn.close()
