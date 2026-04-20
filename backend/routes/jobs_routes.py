import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from middleware.entra_auth import get_current_user
from services.jobs import get_job, get_jobs_paged

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
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
