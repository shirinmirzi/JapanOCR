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
):
    merged_metadata = dict(metadata) if metadata else {}
    if renamed_filename is not None:
        merged_metadata["renamed_filename"] = renamed_filename
    if folder_name is not None:
        merged_metadata["folder_name"] = folder_name
    if execution_folder is not None:
        merged_metadata["execution_folder"] = execution_folder
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
) -> int | None:
    """Insert a 'processing' log entry and return its id for later update."""
    merged_metadata = {}
    if folder_name is not None:
        merged_metadata["folder_name"] = folder_name
    if execution_folder is not None:
        merged_metadata["execution_folder"] = execution_folder
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
    """Update an existing log entry's status and metadata in place."""
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
) -> dict:
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
        conditions.append("(filename ILIKE %s OR message ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])

    if since:
        conditions.append("timestamp >= %s")
        params.append(since)

    if until:
        conditions.append("timestamp <= %s")
        params.append(until)

    if user_id:
        conditions.append("user_id = %s")
        params.append(user_id)

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


def get_logs_db(limit: int = 100, user_id: str = None) -> list:
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
