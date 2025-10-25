#!/usr/bin/env python3
"""
Metrics Collector Service
Background service that polls MCP server and stores metrics to SQLite
"""

import asyncio
import time
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import traceback
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

# Import our modules
try:
    # Try relative imports first (when used as module)
    from .mcp_client import MCPClient, get_client
    from .metrics_db import MetricsDatabase, get_db
    from .config import (
        POLL_INTERVAL_SECONDS,
        TRACK_TOKEN_USAGE,
        TRACK_AGENT_PERFORMANCE,
        TRACK_DECISIONS,
        TRACK_TEST_ITERATIONS,
        TRACK_PATTERN_EFFECTIVENESS,
        TOKEN_BUDGET_LIMIT
    )
except ImportError:
    # Fall back to direct imports (when run as script)
    from mcp_client import MCPClient, get_client
    from metrics_db import MetricsDatabase, get_db
    from config import (
        POLL_INTERVAL_SECONDS,
        TRACK_TOKEN_USAGE,
        TRACK_AGENT_PERFORMANCE,
        TRACK_DECISIONS,
        TRACK_TEST_ITERATIONS,
        TRACK_PATTERN_EFFECTIVENESS,
        TOKEN_BUDGET_LIMIT
    )


class PhaseFileWatcher(FileSystemEventHandler):
    """
    Watches .context-foundry/current-phase.json files for changes.
    Triggers metrics collection when phase data updates.
    """

    def __init__(self, collector: 'MetricsCollector'):
        super().__init__()
        self.collector = collector
        self.debounce_timers = {}  # Debounce rapid changes
        self.debounce_delay = 0.1  # 100ms
        self.loop = None  # asyncio event loop

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        # Only watch current-phase.json files
        if not event.src_path.endswith('current-phase.json'):
            return

        # Debounce rapid changes
        file_path = event.src_path

        # Cancel existing timer for this file
        if file_path in self.debounce_timers:
            self.debounce_timers[file_path].cancel()

        # Create new timer
        timer = threading.Timer(
            self.debounce_delay,
            self._handle_phase_update,
            args=[file_path]
        )
        timer.start()
        self.debounce_timers[file_path] = timer

    def _handle_phase_update(self, file_path: str):
        """Handle debounced phase file update."""
        print(f"📂 Detected phase file change: {file_path}")

        try:
            # Read phase data
            with open(file_path, 'r') as f:
                phase_data = json.load(f)

            # Extract session info
            session_id = phase_data.get('session_id', 'unknown')

            # Trigger metrics collection for this session
            # Schedule coroutine in the collector's event loop
            if self.collector.loop:
                asyncio.run_coroutine_threadsafe(
                    self.collector.collect_live_phase_update(session_id, phase_data),
                    self.collector.loop
                )
        except Exception as e:
            print(f"⚠️  Error handling phase update: {e}")
            traceback.print_exc()


class MetricsCollector:
    """
    Background service that collects metrics from MCP tasks.

    Runs in a loop:
    1. Poll MCP for active tasks
    2. Get detailed status for each task
    3. Extract metrics
    4. Store to SQLite
    5. Sleep for poll_interval
    6. Repeat
    """

    def __init__(
        self,
        mcp_client: Optional[MCPClient] = None,
        db: Optional[MetricsDatabase] = None,
        poll_interval: float = POLL_INTERVAL_SECONDS
    ):
        """
        Initialize metrics collector.

        Args:
            mcp_client: MCP client instance (or use singleton)
            db: Database instance (or use singleton)
            poll_interval: How often to poll (in seconds)
        """
        self.mcp_client = mcp_client or get_client()
        self.db = db or get_db()
        self.poll_interval = poll_interval
        self.running = False
        self.tracked_tasks = set()  # Tasks we're currently tracking
        self.observer = None  # Watchdog observer
        self.watcher = None   # FileSystemEventHandler
        self.watched_dirs = set()  # Directories being watched
        self.loop = None  # asyncio event loop

    async def start(self):
        """Start the collector service with filesystem watching."""
        self.running = True
        self.loop = asyncio.get_event_loop()  # Store event loop for cross-thread access
        print(f"🔄 Metrics Collector started (poll interval: {self.poll_interval}s)")

        # Start filesystem watcher
        self.start_file_watcher()

        while self.running:
            try:
                await self.collect_metrics()
            except Exception as e:
                print(f"❌ Error in metrics collection: {e}")
                traceback.print_exc()

            # Sleep until next poll
            await asyncio.sleep(self.poll_interval)

    def stop(self):
        """Stop the collector service."""
        self.running = False

        if self.observer:
            self.observer.stop()
            self.observer.join()

        print("🛑 Metrics Collector stopped")

    def start_file_watcher(self):
        """Start watching for .context-foundry/current-phase.json changes."""
        self.watcher = PhaseFileWatcher(self)
        self.watcher.loop = self.loop  # Give watcher access to event loop
        self.observer = Observer()

        # Watch common build directories
        watch_paths = [
            Path.home() / "homelab",  # Common build location
            Path.cwd(),                # Current directory
        ]

        # Also watch checkpoints directory if it exists
        checkpoints_dir = Path("checkpoints/ralph")
        if checkpoints_dir.exists():
            watch_paths.append(checkpoints_dir)

        for watch_path in watch_paths:
            if watch_path.exists():
                try:
                    self.observer.schedule(
                        self.watcher,
                        str(watch_path),
                        recursive=True
                    )
                    self.watched_dirs.add(str(watch_path))
                    print(f"👁️  Watching: {watch_path}")
                except Exception as e:
                    print(f"⚠️  Could not watch {watch_path}: {e}")

        self.observer.start()
        print("✅ Filesystem watcher started")

    async def collect_metrics(self):
        """
        Collect metrics from all active tasks.

        This is the main collection loop.
        """
        # Get all active tasks from MCP
        tasks = self.mcp_client.list_active_tasks()

        for task in tasks:
            task_id = task["task_id"]

            # Ensure task is in database
            if task_id not in self.tracked_tasks:
                await self.initialize_task(task)
                self.tracked_tasks.add(task_id)

            # Update task status
            await self.update_task_status(task)

            # Collect various metrics
            await self.collect_task_metrics(task)

            # Check if task is complete
            if task.get("status") in ["completed", "failed", "timeout"]:
                await self.finalize_task(task)
                self.tracked_tasks.discard(task_id)

    async def initialize_task(self, task: Dict[str, Any]):
        """
        Initialize a new task in the database.

        Args:
            task: Task data from MCP
        """
        print(f"📝 Initializing task: {task['task_id']}")

        try:
            self.db.create_task({
                'task_id': task['task_id'],
                'project_name': task.get('project_name', 'Unknown'),
                'task_description': task.get('task', task.get('task_description', '')),
                'working_directory': task.get('working_directory', task.get('cwd', '')),
                'status': task.get('status', 'running'),
                'phases_completed': task.get('phases_completed', []),
                'current_phase': task.get('current_phase', 'Unknown'),
                'start_time': task.get('start_time', datetime.now().isoformat())
            })
        except Exception as e:
            print(f"⚠️  Error initializing task {task['task_id']}: {e}")

    async def update_task_status(self, task: Dict[str, Any]):
        """
        Update task status in database.

        Args:
            task: Task data from MCP
        """
        try:
            updates = {
                'status': task.get('status', 'running'),
                'current_phase': task.get('current_phase', 'Unknown'),
                'phases_completed': json.dumps(task.get('phases_completed', []))
            }

            # Add end time if complete
            if task.get('status') in ['completed', 'failed', 'timeout']:
                updates['end_time'] = datetime.now().isoformat()
                updates['duration_seconds'] = task.get('elapsed_seconds', 0)

            # Add GitHub URL if available
            if 'github_url' in task:
                updates['github_url'] = task['github_url']

            self.db.update_task(task['task_id'], updates)
        except Exception as e:
            print(f"⚠️  Error updating task {task['task_id']}: {e}")

    async def collect_live_phase_update(self, session_id: str, phase_data: Dict):
        """
        Collect metrics from live phase update (triggered by file watcher).

        Args:
            session_id: Session ID from phase data
            phase_data: Parsed current-phase.json content
        """
        print(f"📊 Collecting metrics for live session: {session_id}")

        # Create simplified task object from phase data
        task = {
            'task_id': session_id,
            'status': phase_data.get('status', 'running'),
            'current_phase': phase_data.get('current_phase', 'Unknown'),
            'phases_completed': phase_data.get('phases_completed', []),
            'test_iteration': phase_data.get('test_iteration', 0),
            'start_time': phase_data.get('started_at'),
            # Try to infer working directory - look for .context-foundry nearby
            'working_directory': str(Path.cwd())  # Default to current directory
        }

        # Try to find actual working directory from session_id
        potential_paths = [
            Path.home() / "homelab" / session_id,
            Path.cwd() / session_id,
            Path.cwd()  # Current directory might be the project itself
        ]

        for potential_path in potential_paths:
            if (potential_path / ".context-foundry" / "current-phase.json").exists():
                task['working_directory'] = str(potential_path)
                break

        # Initialize task if new
        if session_id not in self.tracked_tasks:
            await self.initialize_task(task)
            self.tracked_tasks.add(session_id)

        # Update task status
        await self.update_task_status(task)

        # Collect metrics
        await self.collect_task_metrics(task)

    async def collect_task_metrics(self, task: Dict[str, Any]):
        """
        Collect all metrics for a task.

        Args:
            task: Task data from MCP
        """
        task_id = task['task_id']

        # Collect token usage metrics
        if TRACK_TOKEN_USAGE:
            await self.collect_token_metrics(task)

        # Collect agent performance
        if TRACK_AGENT_PERFORMANCE:
            await self.collect_agent_metrics(task)

        # Collect decision data
        if TRACK_DECISIONS:
            await self.collect_decision_metrics(task)

        # Collect test iterations
        if TRACK_TEST_ITERATIONS:
            await self.collect_test_metrics(task)

        # Collect pattern effectiveness
        if TRACK_PATTERN_EFFECTIVENESS:
            await self.collect_pattern_metrics(task)

    async def collect_token_metrics(self, task: Dict[str, Any]):
        """
        Collect token usage metrics.

        Args:
            task: Task data
        """
        try:
            task_id = task['task_id']

            # Get token estimate
            token_data = self.mcp_client.estimate_token_usage(task_id)

            # Get real latency from metrics DB
            avg_latency_ms = 0
            try:
                from tools.metrics.metrics_db import get_metrics_db

                metrics_db = get_metrics_db()
                phase_stats = metrics_db.get_phase_totals(task.get('current_phase', 'Unknown'), days=7)
                avg_latency_ms = phase_stats.get('avg_latency_ms', 0)
            except ImportError:
                # Metrics module not available
                pass

            # Store metric
            self.db.add_metric(task_id, {
                'timestamp': datetime.now().isoformat(),
                'phase': task.get('current_phase', 'Unknown'),
                'token_usage': token_data['estimated_tokens'],
                'token_percentage': token_data['percentage'],
                'latency_ms': avg_latency_ms,
                'context_resets': task.get('iterations', 0),
                'elapsed_seconds': task.get('elapsed_seconds', 0),
                'estimated_remaining_seconds': task.get('estimated_remaining_seconds', 0)
            })
        except Exception as e:
            print(f"⚠️  Error collecting token metrics: {e}")

    async def collect_agent_metrics(self, task: Dict[str, Any]):
        """
        Collect agent performance metrics.

        Args:
            task: Task data
        """
        try:
            task_id = task['task_id']
            working_dir = task.get('working_directory', task.get('cwd'))

            if not working_dir:
                return

            # Read agent performance from .context-foundry/build-log.md
            # This is a simplified version - full implementation would parse logs
            current_phase = task.get('current_phase', 'Unknown')

            # Check if this phase is new (we haven't recorded it yet)
            existing = self.db.get_agent_performance(task_id)
            phase_recorded = any(
                p.get('phase') == current_phase
                for p in existing
            )

            if not phase_recorded and current_phase in ['Scout', 'Architect', 'Builder', 'Test']:
                # Record agent activity for this phase
                self.db.add_agent_performance(task_id, {
                    'agent_type': current_phase,
                    'phase': current_phase,
                    'start_time': datetime.now().isoformat(),
                    'end_time': None,  # Will update when phase completes
                    'duration_seconds': None,
                    'success': None,  # Will update when complete
                    'issues_found': 0,
                    'issues_fixed': 0,
                    'files_created': 0,
                    'files_modified': 0,
                    'tokens_used': 0
                })
        except Exception as e:
            print(f"⚠️  Error collecting agent metrics: {e}")

    async def collect_decision_metrics(self, task: Dict[str, Any]):
        """
        Collect autonomous decision metrics.

        Args:
            task: Task data
        """
        try:
            task_id = task['task_id']
            working_dir = task.get('working_directory', task.get('cwd'))

            if not working_dir:
                return

            # Read decisions from feedback files
            feedback_dir = Path(working_dir) / ".context-foundry" / "feedback"
            if not feedback_dir.exists():
                return

            for feedback_file in feedback_dir.glob("build-feedback-*.json"):
                try:
                    with open(feedback_file, 'r') as f:
                        feedback = json.load(f)

                    # Process decisions from feedback
                    for issue in feedback.get("issues_found", []):
                        # Example decision record
                        self.db.add_decision(task_id, {
                            'timestamp': feedback.get('timestamp', datetime.now().isoformat()),
                            'phase': issue.get('detected_in_phase', 'Unknown'),
                            'decision_type': 'issue_resolution',
                            'decision_description': issue.get('issue', ''),
                            'quality_rating': 3,  # Default - would need analysis
                            'difficulty_rating': 3,
                            'is_regrettable': False,
                            'used_lessons_learned': bool(issue.get('applies_to_phases')),
                            'pattern_ids': [issue.get('id', '')],
                            'reasoning': issue.get('solution', ''),
                            'outcome': 'applied'
                        })
                except Exception as e:
                    print(f"⚠️  Error reading feedback file {feedback_file}: {e}")
        except Exception as e:
            print(f"⚠️  Error collecting decision metrics: {e}")

    async def collect_test_metrics(self, task: Dict[str, Any]):
        """
        Collect test iteration metrics.

        Args:
            task: Task data
        """
        try:
            task_id = task['task_id']
            working_dir = task.get('working_directory', task.get('cwd'))

            if not working_dir:
                return

            # Check test iteration count
            context_dir = Path(working_dir) / ".context-foundry"
            if not context_dir.exists():
                return

            # Read test iteration files
            for i in range(1, 10):  # Check up to 10 iterations
                test_file = context_dir / f"test-results-iteration-{i}.md"
                if not test_file.exists():
                    break

                # Check if we've already recorded this iteration
                existing = self.db.get_test_iterations(task_id)
                if any(t.get('iteration_number') == i for t in existing):
                    continue

                # Read test results (simplified)
                with open(test_file, 'r') as f:
                    content = f.read()

                # Parse test results (basic parsing)
                tests_passed = content.count('✓') + content.count('PASS')
                tests_failed = content.count('✗') + content.count('FAIL')

                self.db.add_test_iteration(task_id, {
                    'iteration_number': i,
                    'timestamp': datetime.now().isoformat(),
                    'tests_run': tests_passed + tests_failed,
                    'tests_passed': tests_passed,
                    'tests_failed': tests_failed,
                    'test_output': content[:500],  # First 500 chars
                    'fixes_applied': [],
                    'duration_seconds': 0
                })
        except Exception as e:
            print(f"⚠️  Error collecting test metrics: {e}")

    async def collect_pattern_metrics(self, task: Dict[str, Any]):
        """
        Collect pattern effectiveness metrics.

        Args:
            task: Task data
        """
        try:
            task_id = task['task_id']
            working_dir = task.get('working_directory', task.get('cwd'))

            if not working_dir:
                return

            # Read pattern data
            patterns_dir = Path(working_dir) / ".context-foundry" / "patterns"
            if not patterns_dir.exists():
                return

            common_issues_file = patterns_dir / "common-issues.json"
            if common_issues_file.exists():
                with open(common_issues_file, 'r') as f:
                    patterns_data = json.load(f)

                for pattern in patterns_data.get("patterns", []):
                    # Check if we've already recorded this pattern
                    existing = self.db.get_pattern_effectiveness(task_id)
                    if any(
                        p.get('pattern_id') == pattern.get('pattern_id')
                        for p in existing
                    ):
                        continue

                    self.db.add_pattern_effectiveness(task_id, {
                        'pattern_id': pattern.get('pattern_id', ''),
                        'pattern_type': 'common-issue',
                        'was_applied': pattern.get('auto_apply', False),
                        'prevented_issue': True,  # Assume patterns prevent issues
                        'issue_description': pattern.get('issue', ''),
                        'timestamp': datetime.now().isoformat()
                    })
        except Exception as e:
            print(f"⚠️  Error collecting pattern metrics: {e}")

    async def finalize_task(self, task: Dict[str, Any]):
        """
        Finalize task - called when task completes.

        Args:
            task: Completed task data
        """
        task_id = task['task_id']
        print(f"✅ Finalizing task: {task_id} (status: {task.get('status')})")

        # Update task with final data
        await self.update_task_status(task)

        # Collect final metrics
        await self.collect_task_metrics(task)


# ============================================================================
# Standalone Service
# ============================================================================

async def run_collector_service():
    """Run the metrics collector as a standalone service."""
    collector = MetricsCollector()

    print("🚀 Starting Metrics Collector Service")
    print(f"📊 Poll Interval: {POLL_INTERVAL_SECONDS}s")
    print(f"💾 Database: {get_db().db_path}")
    print("Press Ctrl+C to stop\n")

    try:
        await collector.start()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        collector.stop()


if __name__ == "__main__":
    # Run as standalone service
    asyncio.run(run_collector_service())
