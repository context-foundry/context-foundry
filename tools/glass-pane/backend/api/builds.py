"""
Build Control API endpoints for Forge interface.

Provides endpoints for starting and managing Context Foundry builds
directly from the Glass Pane chat interface.
"""

import logging
import subprocess
import json
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/builds", tags=["builds"])

# Compute path to cfd script relative to this file
# This file: tools/glass-pane/backend/api/builds.py
# cfd script: tools/cfd
API_DIR = Path(__file__).parent  # tools/glass-pane/backend/api
BACKEND_DIR = API_DIR.parent  # tools/glass-pane/backend
GLASS_PANE_DIR = BACKEND_DIR.parent  # tools/glass-pane
TOOLS_DIR = GLASS_PANE_DIR.parent  # tools/
CFD_PATH = TOOLS_DIR / "cfd"


class StartBuildRequest(BaseModel):
    """Request to start a new build."""

    task: str = Field(..., description="Build task description", min_length=10)
    working_directory: str = Field(..., description="Working directory for build")
    mode: str = Field(
        "new_project", description="Build mode: new_project, incremental, existing_repo"
    )
    timeout_minutes: int = Field(30, description="Timeout in minutes", ge=5, le=180)
    use_parallel: Optional[bool] = Field(
        None, description="Enable parallel builds (None = auto-detect)"
    )
    github_repo_name: Optional[str] = Field(
        None, description="GitHub repo name for deployment"
    )


class StartBuildResponse(BaseModel):
    """Response after starting a build."""

    success: bool
    job_id: Optional[str]
    message: str
    status: Optional[str]


class CancelBuildResponse(BaseModel):
    """Response after canceling a build."""

    success: bool
    message: str


@router.post("/start", response_model=StartBuildResponse)
async def start_build(request: StartBuildRequest):
    """
    Start a new autonomous build using Context Foundry daemon.

    Submits a build job to the CF daemon and returns the job ID
    for tracking progress.
    """
    try:
        # Validate cfd path exists
        if not CFD_PATH.exists():
            raise HTTPException(
                status_code=500, detail=f"CF daemon script not found at {CFD_PATH}"
            )

        # Build cfd submit command
        cmd = [
            str(CFD_PATH),
            "submit",
            "--type",
            "autonomous_build",
            "--params",
            json.dumps(
                {
                    "task": request.task,
                    "working_directory": request.working_directory,
                    "mode": request.mode,
                    "timeout_minutes": request.timeout_minutes,
                    "use_parallel": request.use_parallel,
                    "github_repo_name": request.github_repo_name,
                }
            ),
        ]

        logger.info(f"Starting build: {request.task[:50]}... using {CFD_PATH}")

        # Execute command
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            logger.error(f"Build submission failed: {result.stderr}")
            raise HTTPException(
                status_code=500, detail=f"Failed to start build: {result.stderr}"
            )

        # Parse output to extract job ID
        # Expected output: "Job submitted: {job_id}\n..."
        output_lines = result.stdout.strip().split("\n")
        job_id = None

        for line in output_lines:
            if "Job submitted:" in line or "job_id" in line.lower():
                # Try to extract UUID
                import re

                uuid_pattern = (
                    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
                )
                match = re.search(uuid_pattern, line, re.IGNORECASE)
                if match:
                    job_id = match.group(0)
                    break

        if not job_id:
            # Fallback: try to parse as JSON
            try:
                output_json = json.loads(result.stdout)
                job_id = output_json.get("job_id")
            except json.JSONDecodeError:
                logger.warning(
                    f"Could not parse job ID from output: {result.stdout[:200]}"
                )

        return StartBuildResponse(
            success=True,
            job_id=job_id,
            message="Build started successfully"
            + (f" (Job ID: {job_id})" if job_id else ""),
            status="queued",
        )

    except subprocess.TimeoutExpired:
        logger.error("Build submission timed out")
        raise HTTPException(status_code=504, detail="Build submission timed out")

    except Exception as e:
        logger.error(f"Error starting build: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{job_id}/cancel", response_model=CancelBuildResponse)
async def cancel_build(job_id: str):
    """
    Cancel a running build.

    Stops the specified build job using the CF daemon cancel command.
    """
    try:
        cmd = [str(CFD_PATH), "cancel", job_id]

        logger.info(f"Canceling build: {job_id} using {CFD_PATH}")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            logger.error(f"Build cancellation failed: {result.stderr}")
            raise HTTPException(
                status_code=500, detail=f"Failed to cancel build: {result.stderr}"
            )

        return CancelBuildResponse(
            success=True, message=f"Build {job_id} cancelled successfully"
        )

    except subprocess.TimeoutExpired:
        logger.error("Build cancellation timed out")
        raise HTTPException(status_code=504, detail="Cancellation timed out")

    except Exception as e:
        logger.error(f"Error canceling build: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active")
async def get_active_builds():
    """
    Get list of currently active (running/queued) builds.

    This endpoint can be used to show active builds in the Forge UI.
    Note: This is handled by the existing /api/jobs endpoint with status filter.
    This is a convenience wrapper.
    """
    try:
        # Import here to avoid circular dependency
        from services.store_service import StoreService
        from config import settings

        store = StoreService(settings.expanded_db_path)

        # Get running builds
        running_jobs, _ = store.list_jobs(status="running", limit=50)

        # Get queued builds
        queued_jobs, _ = store.list_jobs(status="queued", limit=50)

        return {
            "success": True,
            "running": [
                {
                    "id": job.id,
                    "type": job.type,
                    "status": job.status,
                    "created_at": job.created_at,
                    "working_directory": job.params.get("working_directory")
                    if job.params
                    else None,
                }
                for job in running_jobs
            ],
            "queued": [
                {
                    "id": job.id,
                    "type": job.type,
                    "status": job.status,
                    "created_at": job.created_at,
                    "working_directory": job.params.get("working_directory")
                    if job.params
                    else None,
                }
                for job in queued_jobs
            ],
            "total_active": len(running_jobs) + len(queued_jobs),
        }

    except Exception as e:
        logger.error(f"Error getting active builds: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
