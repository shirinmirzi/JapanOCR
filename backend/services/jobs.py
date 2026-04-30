"""
Japan OCR Tool - Job Management Service

Data-access layer for the jobs table. Tracks the lifecycle of bulk-upload
processing batches from creation through completion, including per-file
result storage and progress counters.

Key Features:
- Job lifecycle: create → processing → done/partial/failed state transitions
- Progress tracking: atomic processed_count increment per completed file
- Paginated listing: filterable by status and user with sort support
- Partial results: intermediate result snapshots written during processing

Dependencies: psycopg2 (via config.database)
Author: SHIRIN MIRZI M K
"""

import json
import logging
import uuid

from config.database import execute_query, execute_write

logger = logging.getLogger(__name__)


def create_job(filenames: list, user_id: str = None, batch_name: str = None) -> str:
    """
    Create a new job record in the 'queued' state and return its UUID.

    Args:
        filenames: List of original filenames included in this batch.
        user_id: Username of the user who initiated the upload.
        batch_name: Optional human-readable label for the batch.

    Returns:
        UUID string identifying the newly created job.
    """
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
    """
    Update the status (and optional error message) of an existing job.

    Args:
        job_id: UUID of the job to update.
        status: New status string (e.g. "processing", "done", "failed").
        error: Optional error description to store alongside the status.
    """
    execute_write(
        "UPDATE jobs SET status = %s, error = %s WHERE id = %s",
        (status, error, job_id),
    )


def increment_processed(job_id: str):
    """
    Atomically increment the processed_count for a job by one.

    Args:
        job_id: UUID of the job whose counter should be incremented.
    """
    execute_write(
        "UPDATE jobs SET processed_count = processed_count + 1 WHERE id = %s",
        (job_id,),
    )


def set_job_results(job_id: str, results: dict):
    """
    Persist a per-file result snapshot to the job's results JSONB column.

    Args:
        job_id: UUID of the job to update.
        results: Dict mapping filename strings to per-file result dicts
            (keys: status, error, renamed_filename, output_folder, etc.).
    """
    execute_write(
        "UPDATE jobs SET results = %s::jsonb WHERE id = %s",
        (json.dumps(results), job_id),
    )


def get_job(job_id: str) -> dict:
    """
    Fetch a single job record by its UUID.

    Args:
        job_id: UUID string of the job to retrieve.

    Returns:
        Job record as a dict, or None when no matching row is found.
    """
    rows = execute_query("SELECT * FROM jobs WHERE id = %s", (job_id,))
    if rows:
        return dict(rows[0])
    return None


def list_jobs(limit: int = 50, user_id: str = None) -> list:
    """
    Return the most recent jobs, optionally scoped to a single user.

    Args:
        limit: Maximum number of jobs to return; defaults to 50.
        user_id: When provided, only jobs belonging to this user are returned.

    Returns:
        List of job dicts ordered by created_at descending.
    """
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
    """
    Return a paginated, filterable list of job records.

    Args:
        page: 1-based page number.
        page_size: Maximum records per page.
        sort_by: Column name to sort by; defaults to "created_at".
        sort_dir: "asc" or "desc" sort direction; defaults to "desc".
        status: Exact status value to filter on (e.g. "done").
        user_id: When provided, only jobs for this user are returned.

    Returns:
        Dict with keys: items (list of job dicts), total, page,
        page_size, and total_pages.
    """
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


def cancel_job(job_id: str) -> bool:
    """
    Atomically transition a job from an active state to 'cancelled'.

    Only jobs currently in 'queued' or 'processing' state can be cancelled.

    Args:
        job_id: UUID of the job to cancel.

    Returns:
        True when the job was found in an active state and successfully
        marked as 'cancelled'; False when the job was already in a terminal
        state or was not found.
    """
    result = execute_write(
        "UPDATE jobs SET status = 'cancelled' WHERE id = %s AND status IN ('queued', 'processing') RETURNING id",
        (job_id,),
    )
    return result is not None


def mark_stale_jobs_interrupted() -> None:
    """
    Mark all jobs stuck in 'processing' or 'queued' as 'interrupted'.

    Called once during application startup to clean up stale job records
    that were left in an active state by a previous server instance (e.g.
    after a crash or a hot-reload). Prevents the UI from showing jobs as
    perpetually running after a server restart.
    """
    execute_write(
        "UPDATE jobs SET status = 'interrupted' WHERE status IN ('processing', 'queued')"
    )
    logger.info("Marked stale processing/queued jobs as interrupted on startup")


def init_db():
    """
    Convenience wrapper that delegates to config.database.init_database.

    Exists so service-level code can trigger schema initialisation without
    importing from the config package directly.
    """
    from config.database import init_database
    init_database()
