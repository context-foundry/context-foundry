"""
Artifact-related API handlers.

Handles serving and saving artifact files from project builds.
"""

import json
import logging
from urllib.parse import parse_qs

from .base import HandlerMixin, validate_artifact_path

logger = logging.getLogger(__name__)


class ArtifactHandlersMixin(HandlerMixin):
    """Mixin providing artifact-related handler methods."""

    # Reference to rfile for reading request body
    rfile: any

    def handle_serve_artifact(self, query: str) -> None:
        """Serve artifact file content. Query: path=<filepath>"""
        # Require auth for reading artifacts (contains potentially sensitive build data)
        if not self.check_auth():
            self.send_json_error(
                401, "Unauthorized: missing or invalid X-CF-Auth header"
            )
            return

        params = parse_qs(query)
        file_path = params.get("path", [None])[0]

        if not file_path:
            self.send_json_error(400, "Missing 'path' parameter")
            return

        # Security: validate and normalize path to prevent traversal
        path = validate_artifact_path(file_path)
        if path is None:
            self.send_json_error(
                403,
                f"Invalid path: must be inside a project with .context-foundry (got: {file_path})",
            )
            return

        try:
            if not path.exists():
                self.send_json_error(404, f"File not found: {file_path}")
                return

            # Limit file size to 1MB
            if path.stat().st_size > 1_000_000:
                self.send_json_error(413, "File too large (max 1MB)")
                return

            content = path.read_text(encoding="utf-8", errors="replace")

            # Determine content type
            suffix = path.suffix.lower()
            content_type = {
                ".md": "text/markdown",
                ".json": "application/json",
                ".txt": "text/plain",
                ".log": "text/plain",
            }.get(suffix, "text/plain")

            self.send_json_response(
                {
                    "path": str(path),
                    "name": path.name,
                    "content": content,
                    "size": len(content),
                    "content_type": content_type,
                }
            )

        except Exception as exc:
            logger.warning("Error serving artifact %s: %s", file_path, exc)
            self.send_json_error(500, str(exc))

    def handle_save_artifact(self) -> None:
        """Save edited artifact file content. POST body: {path, content}"""
        # Require auth for destructive operations
        if not self.check_auth():
            self.send_json_error(
                401, "Unauthorized: missing or invalid X-CF-Auth header"
            )
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 2_000_000:  # 2MB limit
                self.send_json_error(413, "Request body too large (max 2MB)")
                return

            body_raw = self.rfile.read(content_length)
            data = json.loads(body_raw.decode("utf-8"))

            file_path = data.get("path")
            content = data.get("content")

            if not file_path or content is None:
                self.send_json_error(400, "Missing 'path' or 'content' in request body")
                return

            # Security: validate and normalize path to prevent traversal
            path = validate_artifact_path(file_path)
            if path is None:
                self.send_json_error(
                    403,
                    f"Invalid path: must be inside a project with .context-foundry (got: {file_path})",
                )
                return

            if not path.parent.exists():
                self.send_json_error(
                    404, f"Parent directory does not exist: {path.parent}"
                )
                return

            # Write the file
            path.write_text(content, encoding="utf-8")
            logger.info("Artifact saved: %s (%d bytes)", path, len(content))

            self.send_json_response(
                {
                    "success": True,
                    "path": str(path),
                    "size": len(content),
                }
            )

        except json.JSONDecodeError as exc:
            self.send_json_error(400, f"Invalid JSON: {exc}")
        except Exception as exc:
            logger.warning("Error saving artifact: %s", exc)
            self.send_json_error(500, str(exc))

    def handle_job_prompt(self, query: str) -> None:
        """Serve the original prompt/task that started a job. Query: job_id=<id>"""
        params = parse_qs(query)
        job_id = params.get("job_id", [None])[0]

        if not job_id:
            self.send_json_error(400, "Missing 'job_id' parameter")
            return

        job = self.server.context.store.get_job(job_id)
        if not job:
            self.send_json_error(404, f"Job not found: {job_id}")
            return

        # Extract prompt/task info from job params
        prompt_info = {
            "job_id": job.id,
            "task": job.params.get("task"),
            "working_directory": job.params.get("working_directory"),
            "mode": job.params.get("mode"),
            "project_type": job.params.get("project_type"),
            "github_repo": job.params.get("github_repo_name"),
            "metadata": job.metadata,
            "created_at": job.created_at.isoformat(),
        }

        self.send_json_response(prompt_info)
