import uuid
import json
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
