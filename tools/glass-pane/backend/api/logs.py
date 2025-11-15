"""
Log-related API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from models.log import LogListResponse
from services.store_service import StoreService
from config import settings

router = APIRouter(prefix="/api/jobs", tags=["logs"])

# Initialize store service
store = StoreService(settings.expanded_db_path)


@router.get("/{job_id}/logs", response_model=LogListResponse)
async def get_job_logs(
    job_id: str,
    level: Optional[str] = Query(
        None, description="Filter by log level (DEBUG, INFO, WARNING, ERROR)"
    ),
    search: Optional[str] = Query(None, description="Text search in log messages"),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of logs to return"
    ),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    since_id: Optional[int] = Query(
        None, description="Get logs after this ID (for incremental fetches)"
    ),
):
    """
    Get logs for a specific job with optional filtering.

    Path Parameters:
    - job_id: Job UUID

    Query Parameters:
    - level: Filter by log level (DEBUG, INFO, WARNING, ERROR)
    - search: Text search in message content
    - limit: Maximum logs to return (default: 100, max: 1000)
    - offset: Pagination offset (default: 0)
    - since_id: Get logs after this ID for incremental fetching
    """
    # Verify job exists
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    logs, total = store.get_logs(
        job_id=job_id,
        level=level,
        search=search,
        limit=limit,
        offset=offset,
        since_id=since_id,
    )

    return LogListResponse(
        logs=logs,
        total=total,
        limit=limit,
        offset=offset,
    )
