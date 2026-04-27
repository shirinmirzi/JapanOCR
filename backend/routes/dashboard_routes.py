"""
Japan OCR Tool - Dashboard Routes

Aggregates KPI metrics and recent-activity data from the invoices, jobs,
and logs tables into a single summary response for the dashboard UI.

Key Features:
- KPI counters: total invoices, jobs, and log entries (optionally filtered by date)
- Per-status breakdown: invoice counts grouped by processing status
- Recent activity: configurable-limit lists of recent jobs, invoices, and failures
- Optional date filter: all queries accept a 'since' ISO timestamp parameter

Dependencies: FastAPI, config.database, services.file_metadata_client, services.jobs
Author: SHIRIN MIRZI M K
"""

import logging

from fastapi import APIRouter, Depends, Query

from config.database import execute_query
from middleware.entra_auth import get_current_user
from services.file_metadata_client import get_dashboard_stats
from services.jobs import list_jobs

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboard")


@router.get("/summary")
async def get_dashboard_summary(
    jobs_limit: int = Query(5, ge=1, le=50),
    invoices_limit: int = Query(5, ge=1, le=50),
    failures_limit: int = Query(5, ge=1, le=50),
    since: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """
    Aggregate KPI metrics and recent-activity records for the dashboard.

    Args:
        jobs_limit: Maximum number of recent jobs to return (1–50).
        invoices_limit: Maximum number of recent invoices to return (1–50).
        failures_limit: Maximum number of recent failure log entries (1–50).
        since: Optional ISO timestamp; when supplied all counts and recent
            lists are restricted to records created on or after this date.
        user: Injected authenticated user; used for access control only.

    Returns:
        Dict with 'kpis' (invoices_total, jobs_total, logs_total,
        by_status, vendors) and 'recent' (jobs, invoices, failures).
    """
    stats = get_dashboard_stats()
    by_status = stats["by_status"]
    vendors = stats["vendors"]

    if since:
        invoices_total_row = execute_query(
            "SELECT COUNT(*) as total FROM invoices "
            "WHERE status != 'deleted' AND created_at >= %s",
            (since,),
        )
    else:
        invoices_total_row = execute_query(
            "SELECT COUNT(*) as total FROM invoices WHERE status != 'deleted'"
        )
    invoices_total = invoices_total_row[0]["total"] if invoices_total_row else 0

    if since:
        jobs_total_row = execute_query(
            "SELECT COUNT(*) as total FROM jobs WHERE created_at >= %s",
            (since,),
        )
    else:
        jobs_total_row = execute_query("SELECT COUNT(*) as total FROM jobs")
    jobs_total = jobs_total_row[0]["total"] if jobs_total_row else 0

    if since:
        logs_total_row = execute_query(
            "SELECT COUNT(*) as total FROM logs WHERE timestamp >= %s",
            (since,),
        )
    else:
        logs_total_row = execute_query("SELECT COUNT(*) as total FROM logs")
    logs_total = logs_total_row[0]["total"] if logs_total_row else 0

    recent_jobs = list_jobs(limit=jobs_limit)

    if since:
        recent_invoices_rows = execute_query(
            "SELECT * FROM invoices WHERE status != 'deleted' "
            "AND created_at >= %s ORDER BY created_at DESC LIMIT %s",
            (since, invoices_limit),
        )
    else:
        recent_invoices_rows = execute_query(
            "SELECT * FROM invoices WHERE status != 'deleted' "
            "ORDER BY created_at DESC LIMIT %s",
            (invoices_limit,),
        )
    recent_invoices = [dict(r) for r in recent_invoices_rows] if recent_invoices_rows else []

    if since:
        failures_rows = execute_query(
            "SELECT * FROM logs WHERE status IN ('error', 'failed') "
            "AND timestamp >= %s ORDER BY timestamp DESC LIMIT %s",
            (since, failures_limit),
        )
    else:
        failures_rows = execute_query(
            "SELECT * FROM logs WHERE status IN ('error', 'failed') "
            "ORDER BY timestamp DESC LIMIT %s",
            (failures_limit,),
        )
    failures = [dict(r) for r in failures_rows] if failures_rows else []

    return {
        "kpis": {
            "invoices_total": invoices_total,
            "jobs_total": jobs_total,
            "logs_total": logs_total,
            "by_status": by_status,
            "vendors": vendors,
            "do_not_send": stats.get("do_not_send", 0),
        },
        "recent": {
            "jobs": recent_jobs,
            "invoices": recent_invoices,
            "failures": failures,
        },
    }
