"""Data provider for TUI - centralized data access"""

from typing import List, Optional, Dict, Any, Callable
from pathlib import Path
from datetime import datetime, timedelta
import json
import asyncio
import subprocess
import uuid
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .models import BuildStatus, SystemStats, AgentMetrics, BuildSummary
from ..config import TUIConfig


class TUIDataProvider:
    """Centralized data provider for TUI with caching"""

    def __init__(self, config: TUIConfig):
        self.config = config
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, datetime] = {}
        self._file_observer: Optional[Observer] = None
        self._callbacks: List[Callable] = []
        self._running = False

    async def start(self):
        """Start file watchers and background tasks"""
        self._running = True
        self._start_file_watcher()

    async def stop(self):
        """Clean shutdown"""
        self._running = False
        if self._file_observer:
            self._file_observer.stop()
            self._file_observer.join(timeout=2)

    def _start_file_watcher(self):
        """Start watching .context-foundry directories"""
        event_handler = PhaseFileHandler(self._on_file_change)
        self._file_observer = Observer()

        # Watch both project dirs and global dir
        for path in self.config.get_watch_paths():
            if path.exists():
                self._file_observer.schedule(event_handler, str(path), recursive=True)

        self._file_observer.start()

    def _on_file_change(self, filepath: Path):
        """Handle file change events"""
        # Invalidate cache for this file
        cache_key = f"json:{filepath}"
        if cache_key in self._cache:
            del self._cache[cache_key]
            if cache_key in self._cache_ttl:
                del self._cache_ttl[cache_key]

        # Notify listeners
        for callback in self._callbacks:
            try:
                callback()
            except Exception:
                pass  # Ignore callback errors

    def subscribe(self, callback: Callable):
        """Subscribe to data updates"""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unsubscribe(self, callback: Callable):
        """Unsubscribe from data updates"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _get_cache(self, key: str, ttl_seconds: float = 1.5) -> Optional[Any]:
        """Get cached value if still valid"""
        if key not in self._cache:
            return None

        # Check TTL
        cache_time = self._cache_ttl.get(key)
        if cache_time and (datetime.now() - cache_time).total_seconds() > ttl_seconds:
            # Cache expired
            del self._cache[key]
            del self._cache_ttl[key]
            return None

        return self._cache[key]

    def _set_cache(self, key: str, value: Any):
        """Set cache value with timestamp"""
        self._cache[key] = value
        self._cache_ttl[key] = datetime.now()

    async def get_current_build(self, project_dir: Optional[Path] = None) -> Optional[BuildStatus]:
        """Get current build status from current-phase.json"""
        if project_dir is None:
            project_dir = Path.cwd()

        json_file = project_dir / ".context-foundry" / "current-phase.json"

        # Check cache
        cache_key = f"build:{json_file}"
        cached = self._get_cache(cache_key, ttl_seconds=1.0)
        if cached is not None:
            return cached

        # Read from file
        if not json_file.exists():
            return None

        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
            build_status = BuildStatus.from_json(data)
            self._set_cache(cache_key, build_status)
            return build_status
        except (json.JSONDecodeError, OSError, KeyError):
            return None

    async def get_system_stats(self) -> SystemStats:
        """Get system statistics (mock for now)"""
        # Check cache
        cache_key = "system_stats"
        cached = self._get_cache(cache_key, ttl_seconds=5.0)
        if cached is not None:
            return cached

        # TODO: Integrate with metrics DB when available
        # For now, return mock data
        stats = SystemStats(
            total_builds=0,
            active_builds=1 if await self.get_current_build() else 0,
            completed_builds=0,
            failed_builds=0,
            total_tokens_used=0,
            total_cost_usd=0.0,
            avg_build_duration_minutes=0.0,
            last_updated=datetime.now()
        )

        self._set_cache(cache_key, stats)
        return stats

    async def get_agent_metrics(self) -> List[AgentMetrics]:
        """Get agent metrics (mock for now)"""
        # Check cache
        cache_key = "agent_metrics"
        cached = self._get_cache(cache_key, ttl_seconds=2.0)
        if cached is not None:
            return cached

        # TODO: Integrate with MCP/metrics DB
        # For now, return empty list
        metrics: List[AgentMetrics] = []

        self._set_cache(cache_key, metrics)
        return metrics

    async def get_recent_builds(self, limit: int = 10) -> List[BuildSummary]:
        """Get recent build summaries"""
        # Check cache
        cache_key = f"recent_builds:{limit}"
        cached = self._get_cache(cache_key, ttl_seconds=2.0)
        if cached is not None:
            return cached

        # For now, just return current build if available
        builds: List[BuildSummary] = []
        current = await self.get_current_build()

        if current:
            # Calculate duration
            duration = None
            if current.started_at:
                # Make now timezone-aware if started_at is timezone-aware
                now = datetime.now()
                if current.started_at.tzinfo is not None:
                    # Use UTC for timezone-aware comparison
                    from datetime import timezone
                    now = datetime.now(timezone.utc)
                    # Convert started_at to UTC if it has tzinfo
                    started = current.started_at.astimezone(timezone.utc)
                else:
                    started = current.started_at

                elapsed = now - started
                duration = elapsed.total_seconds() / 60.0

            builds.append(BuildSummary(
                session_id=current.session_id,
                status=current.status,
                current_phase=current.current_phase,
                started_at=current.started_at,
                duration_minutes=duration,
                test_iterations=current.test_iteration
            ))

        self._set_cache(cache_key, builds)
        return builds

    async def get_build_logs(self, session_id: str) -> List[str]:
        """Get build logs for a specific session"""
        # Check cache
        cache_key = f"logs:{session_id}"
        cached = self._get_cache(cache_key, ttl_seconds=2.0)
        if cached is not None:
            return cached

        # TODO: Read from actual log files
        logs = [
            f"[INFO] Build started: {session_id}",
            "[INFO] Scout phase: Analyzing requirements...",
            "[INFO] Architect phase: Designing system...",
            "[INFO] Builder phase: Implementing code...",
        ]

        self._set_cache(cache_key, logs)
        return logs

    async def launch_build(
        self,
        task: str,
        working_directory: str,
        github_repo_name: Optional[str] = None,
        mode: str = "new_project",
        enable_test_loop: bool = True,
        max_test_iterations: int = 3,
        timeout_minutes: float = 90.0
    ) -> Dict[str, Any]:
        """
        Launch a new autonomous build using Context Foundry.

        This spawns a claude-code process in the background that will run
        the autonomous build orchestrator.

        Args:
            task: Task description (e.g., "Build a tic-tac-toe game")
            working_directory: Where to create the project
            github_repo_name: Optional GitHub repo name for deployment
            mode: Build mode ("new_project", "fix_bugs", "add_docs")
            enable_test_loop: Enable self-healing test loop
            max_test_iterations: Max test/fix iterations
            timeout_minutes: Build timeout

        Returns:
            Dict with task_id and status
        """
        try:
            # Generate task ID
            task_id = str(uuid.uuid4())

            # Get Context Foundry directory
            cf_dir = Path.home() / 'homelab' / 'context-foundry'
            orchestrator_prompt = cf_dir / 'tools' / 'orchestrator_prompt.txt'

            if not orchestrator_prompt.exists():
                return {
                    "error": f"Orchestrator prompt not found: {orchestrator_prompt}",
                    "status": "failed"
                }

            # Build claude-code command
            # Use the orchestrator prompt with environment variables
            env = {
                **dict(os.environ),
                'CF_TASK': task,
                'CF_WORKING_DIR': working_directory,
                'CF_GITHUB_REPO': github_repo_name or '',
                'CF_MODE': mode,
                'CF_TEST_LOOP': 'true' if enable_test_loop else 'false',
                'CF_MAX_TEST_ITERATIONS': str(max_test_iterations),
                'CF_TIMEOUT_MINUTES': str(timeout_minutes),
                'CF_SESSION_ID': task_id
            }

            # Create build prompt file
            build_prompt = Path(working_directory) / f".launch-{task_id}.txt"
            build_prompt.write_text(f"""Task: {task}
Working Directory: {working_directory}
GitHub Repo: {github_repo_name or 'none'}
Mode: {mode}
Enable Test Loop: {enable_test_loop}
Max Test Iterations: {max_test_iterations}
Session ID: {task_id}

Execute the Context Foundry autonomous build orchestrator.
""")

            # Spawn claude-code process with orchestrator prompt
            log_file = Path(working_directory) / f".launch-{task_id}.log"

            process = subprocess.Popen(
                [
                    "claude-code",
                    "--print",
                    "--system-prompt", str(orchestrator_prompt),
                    f"Build project: {task}. Working directory: {working_directory}. GitHub repo: {github_repo_name or 'skip deployment'}. Session ID: {task_id}"
                ],
                cwd=working_directory,
                stdout=open(log_file, 'w'),
                stderr=subprocess.STDOUT,
                text=True,
                env=env
            )

            # Store build info for tracking
            self._set_cache(f"launched_build:{task_id}", {
                "task_id": task_id,
                "working_directory": working_directory,
                "pid": process.pid,
                "task": task,
                "github_repo": github_repo_name,
                "started_at": datetime.now()
            })

            # Don't wait for completion - return immediately
            return {
                "task_id": task_id,
                "status": "started",
                "working_directory": working_directory,
                "message": f"Build launched in background (PID: {process.pid})",
                "log_file": str(log_file)
            }

        except Exception as e:
            import traceback
            return {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "status": "failed"
            }


class PhaseFileHandler(FileSystemEventHandler):
    """Watch for changes to phase JSON files"""

    def __init__(self, callback: Callable[[Path], None]):
        super().__init__()
        self.callback = callback
        self._last_modified: Dict[str, datetime] = {}

    def on_modified(self, event):
        """Handle file modification events"""
        if event.is_directory:
            return

        # Only process JSON files
        if not event.src_path.endswith('.json'):
            return

        path = Path(event.src_path)

        # Debounce: ignore if modified within last 500ms
        now = datetime.now()
        last_mod = self._last_modified.get(str(path))

        if last_mod and (now - last_mod).total_seconds() < 0.5:
            return

        self._last_modified[str(path)] = now

        # Trigger callback
        try:
            self.callback(path)
        except Exception:
            pass  # Ignore errors in callback

    def on_created(self, event):
        """Handle file creation events"""
        # Treat creation as modification
        self.on_modified(event)
