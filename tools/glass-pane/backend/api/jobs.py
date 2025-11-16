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


@router.get("/{job_id}/phases/detailed")
async def get_job_phases_detailed(job_id: str):
    """
    Get detailed phase breakdown with token usage from session-summary.json.
    Also includes current active phase from current-phase.json.

    Path Parameters:
    - job_id: Job UUID
    """
    from pathlib import Path
    import json
    from services.session_parser import SessionParser

    # Get job to extract working directory
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Get working directory from params
    working_dir = store.get_job_working_directory(job_id)
    if not working_dir:
        return {"phases": [], "total_tokens": 0, "current_phase": None}

    context_foundry_dir = Path(working_dir) / ".context-foundry"

    # Initialize session parser
    parser = SessionParser(context_foundry_dir)

    # Read current active phase from current-phase.json
    current_phase_data = None
    started_at = job.started_at if hasattr(job, "started_at") else None
    current_phase_raw = parser.read_current_phase(job_id, started_at)

    if current_phase_raw:
        current_phase_data = {
            "name": current_phase_raw.get("phase", "Unknown"),
            "status": current_phase_raw.get("status", "active"),
            "description": current_phase_raw.get("description", ""),
            "session_id": current_phase_raw.get("session_id"),
            "test_iteration": current_phase_raw.get("test_iteration", 0),
        }

    # Read completed phases from session-summary.json
    summary_path = context_foundry_dir / "session-summary.json"
    phases = []
    total_tokens = 0
    max_context_window = 200000
    model = "unknown"

    if summary_path.exists():
        try:
            summary_data = json.loads(summary_path.read_text())
            context_metrics = summary_data.get("context_metrics", {})
            by_phase = context_metrics.get("by_phase", {})
            max_context_window = context_metrics.get("max_context_window", 200000)
            model = context_metrics.get("model", "unknown")

            # Transform completed phases to array
            for phase_name, phase_data in by_phase.items():
                tokens = phase_data.get("tokens_used", 0)
                total_tokens += tokens

                phases.append(
                    {
                        "name": phase_name,
                        "status": "completed",
                        "tokens_used": tokens,
                        "percentage": phase_data.get("percentage", 0),
                        "duration_seconds": phase_data.get("duration_seconds", 0),
                        "budget_allocated": phase_data.get("budget_allocated", 0),
                        "over_budget": phase_data.get("over_budget", False),
                        "exit_code": phase_data.get("exit_code", 0),
                        "timestamp": phase_data.get("timestamp", ""),
                    }
                )

            # Sort completed phases by timestamp
            phases.sort(key=lambda p: p["timestamp"])

        except (json.JSONDecodeError, FileNotFoundError):
            # Log but don't fail - current phase might still be available
            pass

    return {
        "phases": phases,
        "current_phase": current_phase_data,
        "total_tokens": total_tokens,
        "max_context_window": max_context_window,
        "model": model,
    }
