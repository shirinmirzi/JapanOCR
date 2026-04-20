import json
import logging
import uuid

from config.database import execute_query, execute_write

logger = logging.getLogger(__name__)


def create_job(filenames: list, user_id: str = None, batch_name: str = None) -> str:
    job_id = str(uuid.uuid4())
    execute_write(
        """
        INSERT INTO jobs (id, user_id, status, total_count, processed_count, filenames, batch_name)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
        """,
        (job_id, user_id, "queued", len(filenames), 0, json.dumps(filenames), batch_name),
    )
    return job_id


def set_job_status(job_id: str, status: str, error: str = None):
    execute_write(
        "UPDATE jobs SET status = %s, error = %s WHERE id = %s",
        (status, error, job_id),
    )


def increment_processed(job_id: str):
    execute_write(
        "UPDATE jobs SET processed_count = processed_count + 1 WHERE id = %s",
        (job_id,),
    )


def set_job_results(job_id: str, results: dict):
    execute_write(
        "UPDATE jobs SET results = %s::jsonb WHERE id = %s",
        (json.dumps(results), job_id),
    )


def get_job(job_id: str) -> dict:
    rows = execute_query("SELECT * FROM jobs WHERE id = %s", (job_id,))
    if rows:
        return dict(rows[0])
    return None


def list_jobs(limit: int = 50, user_id: str = None) -> list:
    if user_id:
        rows = execute_query(
            "SELECT * FROM jobs WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
            (user_id, limit),
        )
    else:
        rows = execute_query(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )
    return [dict(r) for r in rows]


def get_jobs_paged(
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "created_at",
    sort_dir: str = "desc",
    status: str = None,
    user_id: str = None,
) -> dict:
    allowed_sort = {"created_at", "status", "total_count", "processed_count"}
    if sort_by not in allowed_sort:
        sort_by = "created_at"
    sort_dir = "DESC" if sort_dir.lower() == "desc" else "ASC"

    conditions = []
    params = []

    if status:
        conditions.append("status = %s")
        params.append(status)
    if user_id:
        conditions.append("user_id = %s")
        params.append(user_id)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    count_sql = f"SELECT COUNT(*) as total FROM jobs {where}"
    count_row = execute_query(count_sql, params or None)
    total = count_row[0]["total"] if count_row else 0

    offset = (page - 1) * page_size
    data_sql = f"SELECT * FROM jobs {where} ORDER BY {sort_by} {sort_dir} LIMIT %s OFFSET %s"
    rows = execute_query(data_sql, (params or []) + [page_size, offset])
    items = [dict(r) for r in rows]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


def init_db():
    from config.database import init_database
    init_database()
