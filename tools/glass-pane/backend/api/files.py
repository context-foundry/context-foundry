"""
File content API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
import logging

from services.store_service import StoreService
from config import settings

router = APIRouter(prefix="/api/files", tags=["files"])
logger = logging.getLogger(__name__)

# Initialize store service
store = StoreService(settings.expanded_db_path)


@router.get("")
async def get_file_content(
    path: str = Query(
        ..., description="Relative file path (e.g., .context-foundry/scout-report.md)"
    ),
    job_id: str = Query(None, description="Job ID to get working directory from"),
):
    """
    Get file content from project directory.

    Query Parameters:
    - path: Relative file path
    - job_id: Optional job ID to determine working directory

    Security:
    - Path must be relative (no absolute paths)
    - Path cannot escape project directory (no ../)
    - Only files within job's working directory are accessible
    """
    # Security: Prevent path traversal
    if path.startswith("/") or ".." in path:
        raise HTTPException(status_code=403, detail="Invalid file path")

    # Get base directory (either job's working_directory or cwd)
    if job_id:
        working_dir = store.get_job_working_directory(job_id)
        if not working_dir:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} not found or has no working_directory",
            )
        base_dir = Path(working_dir)
    else:
        base_dir = Path.cwd()

    # Resolve file path relative to base directory
    file_path = base_dir / path

    # Security: Ensure resolved path is within project
    try:
        file_path = file_path.resolve()
        base_dir_resolved = base_dir.resolve()

        if not str(file_path).startswith(str(base_dir_resolved)):
            raise HTTPException(
                status_code=403, detail="Path outside project directory"
            )

    except (OSError, RuntimeError) as e:
        logger.error(f"Path resolution error: {e}")
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Check if file exists
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {path}")

    if not file_path.is_file():
        raise HTTPException(status_code=400, detail=f"Path is not a file: {path}")

    # Read file content
    try:
        content = file_path.read_text(encoding="utf-8")
        file_stat = file_path.stat()

        return {
            "path": path,
            "content": content,
            "size": file_stat.st_size,
            "modified_at": file_stat.st_mtime,
        }

    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not a text file")
    except Exception as e:
        logger.error(f"Error reading file {path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read file")


@router.get("/list")
async def list_files(job_id: str = Query(..., description="Job ID to list files from")):
    """
    List all files in a job's working directory.

    Query Parameters:
    - job_id: Job ID to get working directory from

    Returns:
    - Array of file paths relative to working directory

    Security:
    - Only files within job's working directory are listed
    - Excludes .git, .context-foundry, venv, __pycache__, node_modules
    """
    # Get job's working directory
    working_dir = store.get_job_working_directory(job_id)
    if not working_dir:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found or has no working_directory",
        )

    base_dir = Path(working_dir)
    if not base_dir.exists():
        return {"files": []}

    # Directories to exclude (removed .context-foundry to make it browseable)
    exclude_dirs = {
        ".git",
        "venv",
        "__pycache__",
        "node_modules",
        ".DS_Store",
    }

    try:
        files = []
        for file_path in base_dir.rglob("*"):
            # Skip if any parent directory is in exclude list
            if any(ex in file_path.parts for ex in exclude_dirs):
                continue

            # Skip if file itself is in exclude list
            if file_path.name in exclude_dirs:
                continue

            if file_path.is_file():
                # Get relative path from working directory
                relative_path = file_path.relative_to(base_dir)
                files.append(str(relative_path))

        # Sort files alphabetically
        files.sort()

        logger.info(f"Listed {len(files)} files for job {job_id}")

        return {"files": files}

    except Exception as e:
        logger.error(f"Error listing files for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to list files")


@router.get("/current-phase")
async def get_current_phase(job_id: str = Query(..., description="Job ID")):
    """
    Get current phase data from .context-foundry/current-phase.json

    Query Parameters:
    - job_id: Job ID to get phase data from

    Returns:
    - Phase data including phase name, status, description, etc.
    """
    # Get job's working directory
    working_dir = store.get_job_working_directory(job_id)
    if not working_dir:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found or has no working_directory",
        )

    # Build path to current-phase.json
    phase_file = Path(working_dir) / ".context-foundry" / "current-phase.json"

    if not phase_file.exists():
        return {"phase": None, "status": None, "description": "Build not started yet"}

    try:
        import json

        with open(phase_file, "r") as f:
            content = f.read().strip()

        # Handle empty file (being written to)
        if not content:
            return {
                "phase": None,
                "status": "initializing",
                "description": "Phase file is being created",
            }

        phase_data = json.loads(content)
        return phase_data

    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in current-phase.json for job {job_id}: {e}")
        return {
            "phase": None,
            "status": "updating",
            "description": "Phase data is being updated",
        }
    except Exception as e:
        logger.error(f"Error reading current-phase.json for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read phase data")
