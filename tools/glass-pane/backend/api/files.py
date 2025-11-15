"""
File content API endpoints.
"""

from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
import logging

router = APIRouter(prefix="/api/files", tags=["files"])
logger = logging.getLogger(__name__)


@router.get("")
async def get_file_content(
    path: str = Query(..., description="Relative file path (e.g., src/App.tsx)"),
):
    """
    Get file content from project directory.

    Query Parameters:
    - path: Relative file path

    Security:
    - Path must be relative (no absolute paths)
    - Path cannot escape project directory (no ../)
    - Only files within current working directory are accessible
    """
    # Security: Prevent path traversal
    if path.startswith("/") or ".." in path:
        raise HTTPException(status_code=403, detail="Invalid file path")

    # Resolve file path relative to current directory
    file_path = Path.cwd() / path

    # Security: Ensure resolved path is within project
    try:
        file_path = file_path.resolve()
        Path.cwd().resolve()  # Ensure we're comparing absolute paths

        if not str(file_path).startswith(str(Path.cwd().resolve())):
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
