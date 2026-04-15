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
    include_tests: bool = Query(False),
    user_id: str = Query(None),
    user: dict = Depends(get_current_user),
):
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
        include_tests=include_tests,
        user_id=user_id,
    )


@router.get("/diagnostics/timeouts")
async def timeout_diagnostics(
    user: dict = Depends(get_current_user),
):
    return get_timeout_diagnostics()
