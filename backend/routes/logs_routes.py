"""
Japan OCR Tool - Logs Routes

Exposes REST endpoints for querying processing log entries and retrieving
timeout/error diagnostic aggregates.

Key Features:
- GET /logs/db/paged: paginated log listing with rich filter options
- GET /logs/diagnostics/timeouts: aggregated counts for operational monitoring

Dependencies: FastAPI, services.logging_client
Author: SHIRIN MIRZI M K
"""

import logging

from fastapi import APIRouter, Depends, Query

from middleware.entra_auth import get_current_user
from services.logging_client import get_logs_paged, get_timeout_diagnostics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/logs")


@router.get("/db/paged")
async def logs_paged(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query(None),
    statuses: list[str] = Query(None),
    q: str = Query(None),
    since: str = Query(None),
    until: str = Query(None),
    sort_by: str = Query("timestamp"),
    sort_dir: str = Query("desc"),
    user_id: str = Query(None),
    source: str = Query(None),
    module: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """
    Return a paginated, filtered list of processing log entries.

    Returns:
        Paginated response dict (items, total, page, page_size, total_pages).
        Each item includes flattened renamed_filename, folder_name, and
        execution_folder fields extracted from the JSONB metadata column.
    """
    return get_logs_paged(
        page=page,
        page_size=page_size,
        status=status,
        statuses=statuses,
        q=q,
        since=since,
        until=until,
        sort_by=sort_by,
        sort_dir=sort_dir,
        user_id=user_id,
        source=source,
        module=module,
    )


@router.get("/diagnostics/timeouts")
async def timeout_diagnostics(
    user: dict = Depends(get_current_user),
):
    """
    Return aggregated timeout, error, and success counts from the logs table.

    Returns:
        Dict with timeout_count, error_count, success_count, total, and
        last_entry timestamp.
    """
    return get_timeout_diagnostics()
