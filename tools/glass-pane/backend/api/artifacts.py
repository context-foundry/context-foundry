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

    # Find all .md files and important build artifacts
    markdown_files = []

    # Scan for markdown files
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

    # Add important build log files
    important_files = [
        "main-builder.done",
        "build-tasks.json",
        "current-phase.json",
        "session-summary.json",
    ]

    for filename in important_files:
        file_path = context_foundry_dir / filename
        if file_path.exists():
            try:
                stat = file_path.stat()
                markdown_files.append(
                    {
                        "name": file_path.name,
                        "path": str(file_path.relative_to(working_dir)),
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                        "type": _classify_file(file_path.name),
                    }
                )
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                continue

    # Sort by modification time (newest first)
    markdown_files.sort(key=lambda x: x["modified"], reverse=True)

    return {"files": markdown_files}


@router.get("/{job_id}/markdown/{file_name}", response_class=PlainTextResponse)
async def get_markdown_file(job_id: str, file_name: str):
    """
    Get content of a specific markdown file or build artifact.

    Returns raw file content (markdown, JSON, or text).
    """
    # Security: only allow specific file types, no path traversal
    allowed_extensions = [".md", ".json", ".done", ".log", ".txt"]
    if not any(file_name.endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="File type not allowed")

    if "/" in file_name or "\\" in file_name:
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
    elif "deploy" in filename_lower:
        return "deploy"
    elif "screenshot" in filename_lower:
        return "screenshot"
    elif "summary" in filename_lower:
        return "summary"
    else:
        return "other"


def _classify_file(filename: str) -> str:
    """Classify any file type based on name and extension."""
    filename_lower = filename.lower()

    # JSON files
    if filename_lower.endswith(".json"):
        if "build-tasks" in filename_lower:
            return "build-config"
        elif "current-phase" in filename_lower:
            return "phase-status"
        elif "session-summary" in filename_lower:
            return "summary"
        else:
            return "config"

    # Build completion markers
    if filename_lower.endswith(".done"):
        return "build-log"

    # Log files
    if filename_lower.endswith(".log"):
        return "log"

    # Markdown (fallback)
    if filename_lower.endswith(".md"):
        return _classify_markdown_file(filename)

    return "other"
