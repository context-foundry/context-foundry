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
