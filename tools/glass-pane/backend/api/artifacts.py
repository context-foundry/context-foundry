"""
Artifacts API endpoints - serve markdown files and build artifacts.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pathlib import Path
import logging

from services.store_service import StoreService
from config import settings

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])
store = StoreService(settings.expanded_db_path)
logger = logging.getLogger(__name__)


@router.get("/{job_id}/markdown")
async def list_markdown_files(job_id: str):
    """
    List all markdown files in .context-foundry directory for a job.

    Returns list of markdown artifacts with metadata.
    """
    # Get working directory from job
    working_dir = store.get_job_working_directory(job_id)
    if not working_dir:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    context_foundry_dir = Path(working_dir) / ".context-foundry"
    if not context_foundry_dir.exists():
        return {"files": []}

    # Find all .md files
    markdown_files = []
    for md_file in context_foundry_dir.glob("*.md"):
        try:
            stat = md_file.stat()
            markdown_files.append(
                {
                    "name": md_file.name,
                    "path": str(md_file.relative_to(working_dir)),
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "type": _classify_markdown_file(md_file.name),
                }
            )
        except Exception as e:
            logger.error(f"Error reading markdown file {md_file}: {e}")
            continue

    # Sort by modification time (newest first)
    markdown_files.sort(key=lambda x: x["modified"], reverse=True)

    return {"files": markdown_files}


@router.get("/{job_id}/markdown/{file_name}", response_class=PlainTextResponse)
async def get_markdown_file(job_id: str, file_name: str):
    """
    Get content of a specific markdown file.

    Returns raw markdown content.
    """
    # Security: only allow .md files, no path traversal
    if not file_name.endswith(".md") or "/" in file_name or "\\" in file_name:
        raise HTTPException(status_code=400, detail="Invalid file name")

    # Get working directory from job
    working_dir = store.get_job_working_directory(job_id)
    if not working_dir:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    file_path = Path(working_dir) / ".context-foundry" / file_name

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File {file_name} not found")

    try:
        content = file_path.read_text(encoding="utf-8")
        return content
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")


def _classify_markdown_file(filename: str) -> str:
    """Classify markdown file type based on name."""
    filename_lower = filename.lower()

    if "scout" in filename_lower:
        return "scout"
    elif "architect" in filename_lower:
        return "architect"
    elif "test" in filename_lower:
        return "test"
    elif "build" in filename_lower:
        return "build"
    elif "summary" in filename_lower:
        return "summary"
    else:
        return "other"
