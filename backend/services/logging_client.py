"""
Japan OCR Tool - Processing Log Client

Data-access layer for the logs table. Records the start and final outcome
of every invoice processing attempt and exposes paginated, filtered log
queries for the UI and diagnostics endpoints.

Key Features:
- Two-phase logging: log_processing_start creates a 'processing' entry;
  update_log_entry updates it to 'success' or 'error' at completion
- Module tagging: entries carry a module field so invoice and other
  pipeline logs can be filtered independently
- Diagnostics: timeout/error/success counts for operational monitoring
- Startup cleanup: mark_stale_logs_interrupted resets 'processing' entries
  left behind by a crashed or restarted server so the Logs page does not
  show perpetually-active entries after a restart
- Backward compat: log_ocr_result alias preserved for older call sites

Dependencies: psycopg2 (via config.database)
Author: SHIRIN MIRZI M K
"""

import json
import logging

from config.database import execute_query, execute_write

logger = logging.getLogger(__name__)


def log_invoice_result(
    filename: str,
    status: str,
    message: str = None,
    error: str = None,
    metadata: dict = None,
    user_id: str = None,
    renamed_filename: str = None,
    folder_name: str = None,
    execution_folder: str = None,
    module: str = None,
):
    """
    Insert a terminal log entry for a completed invoice processing attempt.

    Args:
        filename: Original uploaded filename.
        status: Final status string ("success", "error", "timeout", etc.).
        message: Optional human-readable success or info message.
        error: Optional error detail string when status indicates failure.
        metadata: Optional dict of arbitrary extra fields merged into the
            JSONB metadata column.
        user_id: Username of the user who triggered the processing.
        renamed_filename: Output filename after OCR-based renaming (daily only).
        folder_name: Output folder name (e.g. "ProcessedFiles", "Error").
        execution_folder: Batch execution folder (e.g. "20250430_143022").
        module: Pipeline module tag (e.g. "invoice") for log filtering.
    """
    merged_metadata = dict(metadata) if metadata else {}
    if renamed_filename is not None:
        merged_metadata["renamed_filename"] = renamed_filename
    if folder_name is not None:
        merged_metadata["folder_name"] = folder_name
    if execution_folder is not None:
        merged_metadata["execution_folder"] = execution_folder
    if module is not None:
        merged_metadata["module"] = module
    try:
        execute_write(
            """
            INSERT INTO logs (filename, status, message, error, metadata, user_id)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                filename,
                status,
                message,
                error,
                json.dumps(merged_metadata) if merged_metadata else None,
                user_id,
            ),
        )
    except Exception as e:
        logger.warning("Failed to write log entry: %s", e)


# Alias for compatibility
log_ocr_result = log_invoice_result


def log_processing_start(
    filename: str,
    user_id: str = None,
    execution_folder: str = None,
    folder_name: str = None,
    module: str = None,
) -> int | None:
    """
    Insert a 'processing' log entry and return its id for later update.

    Args:
        filename: Original uploaded filename being processed.
        user_id: Username of the user who triggered the processing.
        execution_folder: Batch execution folder (e.g. "20250430_143022").
        folder_name: Target output folder name, if known at start time.
        module: Pipeline module tag (e.g. "invoice") for log filtering.

    Returns:
        Integer primary key of the new log row, or None when the insert fails.
    """
    merged_metadata = {}
    if folder_name is not None:
        merged_metadata["folder_name"] = folder_name
    if execution_folder is not None:
        merged_metadata["execution_folder"] = execution_folder
    if module is not None:
        merged_metadata["module"] = module
    try:
        row = execute_write(
            """
            INSERT INTO logs (filename, status, metadata, user_id)
            VALUES (%s, %s, %s::jsonb, %s)
            RETURNING id
            """,
            (
                filename,
                "processing",
                json.dumps(merged_metadata) if merged_metadata else None,
                user_id,
            ),
        )
        if row:
            return row["id"]
    except Exception as e:
        logger.warning("Failed to write processing log entry: %s", e)
    return None


def update_log_entry(
    log_id: int,
    status: str,
    message: str = None,
    error: str = None,
    renamed_filename: str = None,
    folder_name: str = None,
):
    """
    Update an existing log entry's status and metadata in place.

    Merges the new values into the existing JSONB metadata rather than
    replacing it, so fields written at start time (e.g. execution_folder)
    are preserved in the final log record.

    Args:
        log_id: Primary key of the log row to update, as returned by
            log_processing_start.
        status: Terminal status string ("success" or "error").
        message: Optional success or info message.
        error: Optional error detail string.
        renamed_filename: Output filename after OCR-based renaming.
        folder_name: Output folder name written into metadata.
    """
    if log_id is None:
        return
    try:
        rows = execute_query("SELECT metadata FROM logs WHERE id = %s", (log_id,))
        existing_meta = {}
        if rows:
            meta = rows[0].get("metadata") or {}
            if isinstance(meta, str):
                try:
                    existing_meta = json.loads(meta)
                except Exception:
                    existing_meta = {}
            elif isinstance(meta, dict):
                existing_meta = dict(meta)
        if renamed_filename is not None:
            existing_meta["renamed_filename"] = renamed_filename
        if folder_name is not None:
            existing_meta["folder_name"] = folder_name
        execute_write(
            """
            UPDATE logs SET status = %s, message = %s, error = %s,
                metadata = %s::jsonb
            WHERE id = %s
            """,
            (
                status,
                message,
                error,
                json.dumps(existing_meta) if existing_meta else None,
                log_id,
            ),
        )
    except Exception as e:
        logger.warning("Failed to update log entry %s: %s", log_id, e)


def get_logs_paged(
    page: int = 1,
    page_size: int = 20,
    status: str = None,
    statuses: list = None,
    q: str = None,
    since: str = None,
    until: str = None,
    sort_by: str = "timestamp",
    sort_dir: str = "desc",
    user_id: str = None,
    source: str = None,
    module: str = None,
    execution_folder: str = None,
) -> dict:
    """
    Return a paginated, filtered list of log entries.

    Args:
        page: 1-based page number.
        page_size: Maximum records per page.
        status: Exact status to filter on; mutually exclusive with statuses.
        statuses: List of status values to match with SQL IN (...).
        q: Free-text search across filename, message, and metadata text.
        since: ISO timestamp lower bound on the log timestamp (inclusive).
        until: ISO timestamp upper bound on the log timestamp (inclusive).
        sort_by: Column to sort by; defaults to "timestamp".
        sort_dir: "asc" or "desc"; defaults to "desc".
        user_id: When provided, only logs for this user are returned.
        source: Filters on metadata->>'source' or metadata->>'module'.
        module: Module tag filter; "invoice" also includes legacy entries
            that predate module tagging.
        execution_folder: When provided, only entries whose
            metadata->>'execution_folder' matches this value are returned.
            Used by the Logs page to pin to the currently active batch.

    Returns:
        Dict with keys: items (list of log dicts with flattened renamed_filename,
        folder_name, and execution_folder), total, page, page_size, total_pages.
    """
    allowed_sort = {"timestamp", "filename", "status"}
    if sort_by not in allowed_sort:
        sort_by = "timestamp"
    sort_dir = "DESC" if sort_dir.lower() == "desc" else "ASC"

    conditions = []
    params = []

    if status:
        conditions.append("status = %s")
        params.append(status)
    elif statuses:
        placeholders = ", ".join(["%s"] * len(statuses))
        conditions.append(f"status IN ({placeholders})")
        params.extend(statuses)

    if q:
        conditions.append(
            "(filename ILIKE %s OR message ILIKE %s OR metadata::text ILIKE %s)"
        )
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])

    if since:
        conditions.append("timestamp >= %s")
        params.append(since)

    if until:
        conditions.append("timestamp <= %s")
        params.append(until)

    if user_id:
        conditions.append("user_id = %s")
        params.append(user_id)

    if source:
        conditions.append(
            "(metadata->>'source' = %s OR metadata->>'module' = %s)"
        )
        params.extend([source, source])

    if module:
        if module == "invoice":
            # Include entries explicitly tagged as 'invoice' OR legacy entries
            # that have no module field at all (pre-module-tagging data).
            conditions.append(
                "(metadata->>'module' = %s OR metadata->>'module' IS NULL)"
            )
            params.append("invoice")
        else:
            conditions.append("metadata->>'module' = %s")
            params.append(module)

    if execution_folder:
        conditions.append("metadata->>'execution_folder' = %s")
        params.append(execution_folder)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    count_sql = f"SELECT COUNT(*) as total FROM logs {where}"
    count_row = execute_query(count_sql, params or None)
    total = count_row[0]["total"] if count_row else 0

    offset = (page - 1) * page_size
    data_sql = f"SELECT * FROM logs {where} ORDER BY {sort_by} {sort_dir} LIMIT %s OFFSET %s"
    rows = execute_query(data_sql, (params or []) + [page_size, offset])
    items = []
    for r in rows:
        item = dict(r)
        meta = item.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        item["renamed_filename"] = meta.get("renamed_filename")
        item["folder_name"] = meta.get("folder_name")
        item["execution_folder"] = meta.get("execution_folder")
        items.append(item)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
    }


def mark_stale_logs_interrupted() -> None:
    """
    Mark all log entries stuck in 'processing' state as 'interrupted'.

    Called once at application startup to clean up log rows that were left
    in the 'processing' state by a previous server instance (e.g. after a
    crash or a hot-reload). Prevents the Logs page from polling indefinitely
    on entries that will never reach a terminal state.
    """
    try:
        execute_write(
            "UPDATE logs SET status = 'interrupted' WHERE status = 'processing'"
        )
        logger.info("Marked stale processing log entries as interrupted on startup")
    except Exception as e:
        logger.warning("Could not mark stale log entries as interrupted: %s", e)


def get_logs_db(limit: int = 100, user_id: str = None) -> list:
    """
    Return the most recent log entries without pagination.

    Args:
        limit: Maximum number of entries to return; defaults to 100.
        user_id: When provided, only logs for this user are returned.

    Returns:
        List of log dicts ordered by timestamp descending.
    """
    if user_id:
        rows = execute_query(
            "SELECT * FROM logs WHERE user_id = %s ORDER BY timestamp DESC LIMIT %s",
            (user_id, limit),
        )
    else:
        rows = execute_query(
            "SELECT * FROM logs ORDER BY timestamp DESC LIMIT %s",
            (limit,),
        )
    return [dict(r) for r in rows]


def get_timeout_diagnostics() -> dict:
    """
    Return aggregated status counts from the logs table for diagnostics.

    Returns:
        Dict with keys: timeout_count, error_count, success_count, total,
        and last_entry (timestamp of the most recent log row).
    """
    rows = execute_query(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'timeout') as timeout_count,
            COUNT(*) FILTER (WHERE status = 'error') as error_count,
            COUNT(*) FILTER (WHERE status = 'success') as success_count,
            COUNT(*) as total,
            MAX(timestamp) as last_entry
        FROM logs
        """,
    )
    if rows:
        return dict(rows[0])
    return {
        "timeout_count": 0,
        "error_count": 0,
        "success_count": 0,
        "total": 0,
        "last_entry": None,
    }
