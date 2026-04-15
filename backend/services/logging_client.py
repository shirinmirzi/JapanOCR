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
):
    try:
        execute_write(
            """
            INSERT INTO logs (filename, status, message, error, metadata, user_id)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            """,
            (filename, status, message, error, json.dumps(metadata) if metadata else None, user_id),
        )
    except Exception as e:
        logger.warning("Failed to write log entry: %s", e)


# Alias for compatibility
log_ocr_result = log_invoice_result


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
    include_tests: bool = False,
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
    items = [dict(r) for r in rows]

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
    return {"timeout_count": 0, "error_count": 0, "success_count": 0, "total": 0, "last_entry": None}
