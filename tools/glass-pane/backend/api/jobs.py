"""
Job-related API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from models.job import JobListResponse, JobDetailResponse
from services.store_service import StoreService
from config import settings

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Initialize store service
store = StoreService(settings.expanded_db_path)


@router.get("", response_model=JobListResponse)
async def list_jobs(
    status: Optional[str] = Query(
        None, description="Filter by status (running, completed, failed)"
    ),
    limit: int = Query(
        50, ge=1, le=200, description="Maximum number of jobs to return"
    ),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """
    List all jobs with optional filtering.

    Query Parameters:
    - status: Filter by job status
    - limit: Maximum jobs to return (default: 50, max: 200)
    - offset: Pagination offset (default: 0)
    """
    jobs, total = store.list_jobs(status=status, limit=limit, offset=offset)

    return JobListResponse(
        jobs=jobs,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(job_id: str):
    """
    Get detailed information about a specific job.

    Path Parameters:
    - job_id: Job UUID
    """
    job = store.get_job_detail(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return job


@router.get("/{job_id}/phase")
async def get_job_phase(job_id: str):
    """
    Get current phase information for a job.

    Path Parameters:
    - job_id: Job UUID
    """
    job = store.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return {
        "job_id": job.id,
        "current_phase": job.current_phase,
        "status": job.status,
    }
