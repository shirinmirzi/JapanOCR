"""
Japan OCR Tool - Jobs Routes

Exposes REST endpoints for querying bulk-upload job records, including
paginated listing and individual job retrieval.

Key Features:
- GET /jobs/paged: paginated, filterable job list with sort support
- GET /jobs/{job_id}: single job detail with 404 guard

Dependencies: FastAPI, services.jobs
Author: SHIRIN MIRZI M K
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from middleware.entra_auth import get_current_user
from services.jobs import cancel_job, get_job, get_jobs_paged

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jobs")


@router.get("/paged")
async def jobs_paged(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc"),
    status: str = Query(None),
    user_id: str = Query(None),
    user: dict = Depends(get_current_user),
):
    """
    Return a paginated list of job records with optional filtering.

    Returns:
        Paginated response dict (items, total, page, page_size, total_pages).
    """
    return get_jobs_paged(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_dir=sort_dir,
        status=status,
        user_id=user_id,
    )


@router.get("/{job_id}")
async def get_job_by_id(
    job_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Return a single job record by its UUID.

    Args:
        job_id: UUID string of the job to retrieve.
        user: Injected authenticated user.

    Returns:
        Job record as a dict.

    Raises:
        HTTPException: 404 when no matching job is found.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/cancel")
async def cancel_job_by_id(
    job_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Request cancellation of an active (queued or processing) bulk job.

    Sets the job status to 'cancelled' in the database. The background
    processing thread checks this status before each file and will stop
    as soon as it picks up the change.

    Args:
        job_id: UUID string of the job to cancel.
        user: Injected authenticated user.

    Returns:
        Dict with 'cancelled' (bool) and 'status' of the job.

    Raises:
        HTTPException: 404 when no matching job is found.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    cancelled = cancel_job(job_id)
    # Fetch once after the update to return the current state.
    updated_job = get_job(job_id) or job
    return {
        "cancelled": cancelled,
        "job_id": job_id,
        "status": updated_job.get("status"),
    }
