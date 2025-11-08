#!/usr/bin/env python3
"""
Evolution Daemon for CFES
Main service orchestrator running continuously
"""

import json
import logging
from logging.handlers import RotatingFileHandler
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from .task_queue import TaskQueueManager, Task, TaskStatus, TaskType
from .resource_manager import ResourceManager
from .process_watchdog import ProcessWatchdog
from .modes.self_improvement import SelfImprovementMode
from .modes.chaos_creative import ChaosCreativeMode
from .modes.research_discovery import ResearchDiscoveryMode


# Setup logging
def setup_logging(log_dir: Path):
    """Setup rotating file logging"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "daemon.log"

    # Set up rotating file handler (10MB per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )

    # Console handler for stdout/stderr
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, console_handler]
    )

    return logging.getLogger(__name__)


class EvolutionDaemon:
    """Main daemon service orchestrator"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize daemon
        
        Args:
            config_path: Path to config file
        """
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Setup logging
        log_dir = Path.home() / ".context-foundry" / "evolution" / "logs"
        self.logger = setup_logging(log_dir)
        
        # Initialize components
        self.task_queue = TaskQueueManager()
        self.resource_manager = ResourceManager(self.config.get('resources', {}))
        self.watchdog = ProcessWatchdog(
            max_duration_minutes=60,
            max_tokens_per_task=100_000,
            check_interval_seconds=30
        )

        # Initialize evolution modes
        self.modes = {
            TaskType.SELF_IMPROVEMENT.value: SelfImprovementMode(),
            TaskType.CHAOS_CREATIVE.value: ChaosCreativeMode(),
            TaskType.RESEARCH.value: ResearchDiscoveryMode()
        }

        # State
        self.running = False
        self.stop_requested = False
        self.active_tasks = {}
        self.poll_count = 0  # Track polling iterations for periodic logging
        self.pid = None
        self.was_paused_for_pr = False  # Track if we were paused for PR review
        self.last_watchdog_check = time.time()  # Track last watchdog check time

        # PID file path
        self.pid_file = Path.home() / ".context-foundry" / "evolution" / "daemon.pid"
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load configuration from file"""
        if config_path is None:
            config_path = Path.home() / ".context-foundry" / "evolution" / "config.json"
        else:
            config_path = Path(config_path)
        
        if not config_path.exists():
            # Return default config
            return {
                "daemon": {
                    "enabled": True,
                    "poll_interval_seconds": 60,
                    "max_concurrent_tasks": 1,
                    "log_level": "INFO"
                },
                "modes": {
                    "self_improvement": {"enabled": True, "priority": 8},
                    "chaos_creative": {"enabled": True, "priority": 5},
                    "research_discovery": {"enabled": False, "priority": 9}
                },
                "resources": {
                    "max_cpu_percent": 80,
                    "max_memory_gb": 16,
                    "active_hours": [6, 22]
                }
            }
        
        with open(config_path) as f:
            return json.load(f)
    
    def _write_pid(self):
        """Write PID to file"""
        self.pid = os.getpid()
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.pid_file, 'w') as f:
            f.write(str(self.pid))
    
    def _remove_pid(self):
        """Remove PID file"""
        if self.pid_file.exists():
            self.pid_file.unlink()
    
    def get_pid(self) -> Optional[int]:
        """Get daemon PID from file"""
        if self.pid_file.exists():
            with open(self.pid_file) as f:
                return int(f.read().strip())
        return None
    
    def is_running(self) -> bool:
        """Check if daemon is running"""
        pid = self.get_pid()
        if pid is None:
            return False
        
        try:
            # Check if process exists
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigint)
        try:
            signal.signal(signal.SIGHUP, self._handle_sighup)
        except AttributeError:
            # SIGHUP not available on Windows
            pass
    
    def _handle_sigterm(self, signum, frame):
        """Handle SIGTERM signal"""
        self.logger.info("Received SIGTERM, initiating graceful shutdown...")
        self.stop_requested = True
    
    def _handle_sigint(self, signum, frame):
        """Handle SIGINT (Ctrl+C)"""
        self.logger.info("Received SIGINT, initiating graceful shutdown...")
        self.stop_requested = True
    
    def _handle_sighup(self, signum, frame):
        """Handle SIGHUP - reload configuration"""
        self.logger.info("Received SIGHUP, reloading configuration...")
        self.config = self._load_config(None)
        self.resource_manager = ResourceManager(self.config.get('resources', {}))
    
    
    def _cleanup_stuck_tasks(self):
        """
        Cleanup any tasks stuck in RUNNING state from previous daemon crash

        This is called on daemon startup to ensure no stuck tasks block the queue.
        Tasks can get stuck in RUNNING state if:
        - Daemon crashed while task was executing
        - Process was killed without cleanup
        - System reboot
        """
        running_tasks = self.task_queue.list_tasks(status=TaskStatus.RUNNING.value, limit=100)

        if running_tasks:
            self.logger.warning(f"Found {len(running_tasks)} stuck RUNNING tasks from previous session - cancelling them")

            for task in running_tasks:
                self.logger.info(f"  Cancelling stuck task: {task.id[:8]} ({task.type}) - started {task.started_at}")
                self.task_queue.update_task_status(
                    task.id,
                    TaskStatus.CANCELLED.value,
                    error="Task was stuck in RUNNING state when daemon restarted"
                )
        else:
            self.logger.debug("No stuck RUNNING tasks found")

    def start(self, daemonize: bool = False):
        """
        Start daemon
        
        Args:
            daemonize: If True, fork and run in background
        """
        if self.is_running():
            self.logger.error("Daemon is already running")
            return False
        
        self._write_pid()
        self.setup_signal_handlers()
        
        # Clean up any stuck tasks from previous crashes
        self._cleanup_stuck_tasks()
        
        self.logger.info(f"Starting Evolution Daemon (PID: {self.pid})")
        self.running = True
        
        try:
            self.main_loop()
        except Exception as e:
            self.logger.error(f"Fatal error in main loop: {e}", exc_info=True)
        finally:
            self.cleanup()
        
        return True
    
    def _check_watchdog(self):
        """
        Check watchdog for stuck/timeout processes and handle actions

        Actions can include:
        - killed_timeout: Process exceeded max duration (60 min)
        - killed_stuck: Process has no log activity (10+ min)
        - process_died: Process terminated unexpectedly
        - warning_tokens: Process exceeding token budget
        """
        actions = self.watchdog.check_processes()

        for action in actions:
            action_type = action.get('action')
            task_id = action.get('task_id')
            pid = action.get('pid')

            if action_type in ['killed_timeout', 'killed_stuck']:
                # Process was killed by watchdog - mark task as failed
                reason = 'timeout' if action_type == 'killed_timeout' else 'stuck (no log activity)'
                duration = action.get('duration_minutes', 0)

                self.logger.error(
                    f"⚠️  Watchdog killed process {pid} (task {task_id[:8]}) - {reason} after {duration:.1f} min"
                )

                # Update task status to FAILED
                self.task_queue.update_task_status(
                    task_id,
                    TaskStatus.FAILED.value,
                    error=f"Process killed by watchdog: {reason} ({duration:.1f} min)"
                )

            elif action_type == 'process_died':
                # Process terminated unexpectedly
                duration = action.get('duration_minutes', 0)
                self.logger.warning(
                    f"Process {pid} (task {task_id[:8]}) died unexpectedly after {duration:.1f} min"
                )
                # Don't update task status - let PR detection handle it (might have succeeded)

            elif action_type == 'warning_tokens':
                # Process using lots of tokens
                estimated = action.get('estimated_tokens', 0)
                self.logger.warning(
                    f"⚠️  Process {pid} (task {task_id[:8]}) estimated {estimated} tokens (high usage)"
                )

    def _interruptible_sleep(self, seconds: int):
        """
        Sleep for specified seconds, but check stop_requested every second
        This makes Ctrl+C responsive instead of blocking for full duration
        """
        for _ in range(seconds):
            if self.stop_requested:
                break
            time.sleep(1)

    def main_loop(self):
        """Main daemon loop - polls queue every 60 seconds"""
        poll_interval = self.config.get('daemon', {}).get('poll_interval_seconds', 60)
        max_concurrent = self.config.get('daemon', {}).get('max_concurrent_tasks', 3)

        # Log polling loop initialization
        self.logger.info(f"Entering main polling loop (interval: {poll_interval}s, max_concurrent: {max_concurrent})")

        while not self.stop_requested:
            try:
                # Check watchdog for stuck/timeout processes (every 30 seconds)
                current_time = time.time()
                if current_time - self.last_watchdog_check >= 30:
                    self._check_watchdog()
                    self.last_watchdog_check = current_time

                # HUMAN-IN-THE-LOOP: Check for open PRs FIRST
                open_prs = self._check_open_prs()

                if open_prs:
                    pr_numbers = [pr['number'] for pr in open_prs]
                    self.logger.info(
                        f"⏸️  PAUSED: Waiting for PR(s) {pr_numbers} to be merged. "
                        f"System will resume when PRs are closed."
                    )
                    self.was_paused_for_pr = True
                    self._interruptible_sleep(poll_interval)
                    continue  # Skip everything - don't pick up tasks!

                # PRs are now closed! Queue next task if we were paused
                if self.was_paused_for_pr:
                    self.logger.info("✅ PRs merged! Queuing next improvement task...")
                    self._queue_next_improvement_task()
                    self.was_paused_for_pr = False

                # GITHUB ISSUE POLLING: Check for new approved issues every cycle
                # This ensures human-approved tasks get added to queue proactively
                self._poll_github_issues()

                # Check resources
                can_accept, resource_status = self.resource_manager.can_accept_task()

                if not can_accept:
                    self.logger.debug(f"Cannot accept tasks: {resource_status}")
                    self._interruptible_sleep(poll_interval)
                    continue

                # Check if we can accept more tasks
                if len(self.active_tasks) >= max_concurrent:
                    self.logger.debug(f"Max concurrent tasks reached ({max_concurrent})")
                    self._interruptible_sleep(poll_interval)
                    continue

                # MCP STATUS MONITORING: Check progress of MCP delegations
                self._check_mcp_status()

                # RACE CONDITION FIX: Detect PRs created by Claude and mark tasks as COMPLETED
                # This allows daemon to pick up next task after PR is created
                self._detect_prs_and_complete_tasks()

                # STUCK TASK PROTECTION: Mark tasks as FAILED if running > 2 hours with no PR
                self._check_stuck_running_tasks()

                # Log queue status before checking for tasks
                pending_count = self.task_queue.count_pending()
                running_count = self.task_queue.count_running()
                self.logger.info(f"Queue status: {pending_count} pending, {running_count} running, {len(self.active_tasks)}/{max_concurrent} active")

                # RACE CONDITION FIX: Don't pick up new tasks if there are RUNNING tasks
                # Running tasks are being executed by background Claude processes
                # We must wait for them to complete (PR created) before starting new ones
                if running_count > 0:
                    self.logger.info(f"⏸️  Waiting for {running_count} running task(s) to complete before picking up new work")
                    self._interruptible_sleep(poll_interval)
                    continue

                # Get next task
                task = self.task_queue.get_next_task()

                if task:
                    self.logger.info(f"Picked up task: {task.id} (type: {task.type})")
                    self._execute_task(task)
                else:
                    # Queue is empty - generate a new improvement task to keep the loop going
                    self.logger.info("No pending tasks in queue - generating new improvement task...")
                    self._queue_next_improvement_task()

                # Sleep before next poll (interruptible for responsive shutdown)
                self._interruptible_sleep(poll_interval)

                # Periodic resource usage logging (every 10 iterations)
                self.poll_count += 1
                if self.poll_count % 10 == 0:
                    usage = self.resource_manager.get_resource_usage()
                    self.logger.info(
                        f"Resource usage [poll #{self.poll_count}] - "
                        f"CPU: {usage['cpu_percent']:.1f}%, "
                        f"Memory: {usage['memory_gb']:.1f}GB ({usage['memory_percent']:.1f}%), "
                        f"Disk: {usage['disk_percent']:.1f}%"
                    )

            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                self._interruptible_sleep(poll_interval)
    
    def _execute_task(self, task: Task):
        """
        Execute task by delegating to appropriate mode

        Args:
            task: Task to execute
        """
        try:
            self.logger.info(f"Executing task {task.id} of type {task.type}")

            # Track active task
            self.active_tasks[task.id] = task

            # Get the appropriate mode for this task type
            mode = self.modes.get(task.type)
            if not mode:
                raise ValueError(f"Unknown task type: {task.type}")

            # Execute task via mode
            self.logger.info(f"Delegating to {task.type} mode")
            task_result = mode.execute_task(task)

            # Validate result
            if mode.validate_result(task_result):
                result = {
                    'status': 'success',
                    'message': f'Task {task.type} executed successfully',
                    'output': task_result.output
                }

                # RACE CONDITION FIX: For self_improvement tasks that spawn Claude or MCP,
                # keep them in RUNNING state until PR is created (don't mark COMPLETED)
                # This prevents daemon from picking up another task before PR is created
                task_status = result.get('output', {}).get('status')
                if task.type == 'self_improvement' and task_status in ['claude_spawned', 'mcp_running']:
                    if task_status == 'mcp_running':
                        mcp_task_id = result['output'].get('mcp_task_id')
                        self.logger.info(f"✅ Task {task.id} delegated to Context Foundry MCP - keeping in RUNNING state until PR detected")
                        self.logger.info(f"   MCP Task ID: {mcp_task_id}")
                        self.logger.info(f"   Monitor: get_delegation_result('{mcp_task_id}')")
                        # Store MCP task_id in task result for monitoring
                        self.task_queue.update_task_status(
                            task.id,
                            TaskStatus.RUNNING.value,
                            result={'mcp_task_id': mcp_task_id, 'branch': result['output'].get('branch')}
                        )
                    else:
                        self.logger.info(f"✅ Task {task.id} delegated to Claude CLI - keeping in RUNNING state until PR detected")
                        self.logger.info(f"   PID: {result['output'].get('pid')}")
                        self.logger.info(f"   Log: {result['output'].get('log_file')}")
                    # Task stays in RUNNING state - will be marked COMPLETED when PR is detected
                else:
                    # For non-delegated tasks, mark as completed immediately
                    self.task_queue.update_task_status(
                        task.id,
                        TaskStatus.COMPLETED.value,
                        result=result
                    )
                    self.logger.info(f"Task {task.id} completed successfully")
            else:
                raise ValueError(f"Task validation failed: {task_result.error}")

        except Exception as e:
            self.logger.error(f"Task {task.id} failed: {e}", exc_info=True)

            # Check if should retry
            if self.task_queue.should_retry(task):
                self.task_queue.retry_task(task.id)
                self.logger.info(f"Task {task.id} will be retried (attempt {task.retry_count + 1}/{task.max_retries})")
            else:
                self.task_queue.update_task_status(
                    task.id,
                    TaskStatus.FAILED.value,
                    error=str(e)
                )

        finally:
            # Remove from active tasks
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]
    
    def stop(self, graceful: bool = True):
        """
        Stop daemon
        
        Args:
            graceful: If True, wait for active tasks to complete
        """
        self.logger.info(f"Stopping daemon (graceful={graceful})")
        
        if graceful:
            # Wait for active tasks
            while self.active_tasks:
                self.logger.info(f"Waiting for {len(self.active_tasks)} active tasks to complete...")
                time.sleep(5)
        
        self.stop_requested = True
        self.running = False
    
    def cleanup(self):
        """Cleanup resources"""
        self.logger.info("Cleaning up daemon resources")
        
        # Close database
        self.task_queue.close()
        
        # Remove PID file
        self._remove_pid()
        
        self.logger.info("Daemon stopped")
    
    def get_uptime(self) -> float:
        """Get daemon uptime in seconds"""
        # Simplified - would track start time
        return 0.0

    def _check_open_prs(self):
        """
        Check for open PRs in the context-foundry repo

        Returns list of open PRs created by the Evolution System
        """
        try:
            # Get git remote to determine GitHub repo
            cf_root = Path(__file__).parent.parent.parent
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                capture_output=True,
                text=True,
                cwd=str(cf_root),
                timeout=5
            )

            if result.returncode != 0:
                self.logger.warning("Could not get git remote URL")
                return []

            remote_url = result.stdout.strip()

            # Parse GitHub owner/repo from remote URL
            # Handle both HTTPS and SSH formats
            if 'github.com' in remote_url:
                if remote_url.startswith('git@github.com:'):
                    # SSH format: git@github.com:owner/repo.git
                    repo_path = remote_url.replace('git@github.com:', '').replace('.git', '')
                elif 'https://github.com/' in remote_url:
                    # HTTPS format: https://github.com/owner/repo.git
                    repo_path = remote_url.replace('https://github.com/', '').replace('.git', '')
                else:
                    self.logger.warning(f"Unrecognized GitHub URL format: {remote_url}")
                    return []

                owner, repo = repo_path.split('/')
            else:
                self.logger.warning("Not a GitHub repository")
                return []

            # Call GitHub API to get open PRs
            api_url = f'https://api.github.com/repos/{owner}/{repo}/pulls'
            params = {'state': 'open'}

            try:
                import requests

                # Try to get GitHub token for authentication (avoids rate limiting)
                # Priority: environment variable > gh CLI > config file
                github_token = os.environ.get('GITHUB_TOKEN')

                if not github_token:
                    # Try to get token from gh CLI (likely already authenticated)
                    try:
                        result = subprocess.run(
                            ['gh', 'auth', 'token'],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            github_token = result.stdout.strip()
                            self.logger.debug("Using GitHub token from gh CLI")
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        pass

                if not github_token:
                    github_token = self.config.get('github', {}).get('token')

                headers = {}
                if github_token:
                    headers['Authorization'] = f'token {github_token}'
                else:
                    self.logger.warning(
                        "No GitHub authentication found. Rate limited to 60 requests/hour. "
                        "Run 'gh auth login' to authenticate."
                    )

                response = requests.get(api_url, params=params, headers=headers, timeout=10)

                # Check for rate limiting
                if response.status_code == 403 and 'rate limit' in response.text.lower():
                    self.logger.warning(
                        "GitHub API rate limit exceeded. "
                        "Set GITHUB_TOKEN environment variable to increase limit to 5000/hour. "
                        "Skipping PR check for this poll cycle."
                    )
                    return []

                response.raise_for_status()
                prs = response.json()

                # Filter for Evolution System PRs
                # Match branches created by Evolution System:
                # - self-improvement/* (primary pattern)
                # - enhancement/* (legacy pattern)
                # - fix/* when created by automation
                evolution_branch_patterns = ['self-improvement/', 'enhancement/', 'fix/']

                evolution_prs = []
                for pr in prs:
                    branch = pr.get('head', {}).get('ref', '')
                    pr_number = pr.get('number', '?')
                    pr_title = pr.get('title', '')[:50]

                    # Check if branch matches any Evolution System pattern
                    is_evolution_pr = any(
                        pattern in branch
                        for pattern in evolution_branch_patterns
                    )

                    if is_evolution_pr:
                        evolution_prs.append(pr)
                        self.logger.debug(
                            f"Found Evolution PR #{pr_number}: {pr_title} (branch: {branch})"
                        )
                    else:
                        self.logger.debug(
                            f"Ignoring non-Evolution PR #{pr_number}: {pr_title} (branch: {branch})"
                        )

                if evolution_prs:
                    self.logger.info(
                        f"Found {len(evolution_prs)} Evolution System PR(s) to wait for"
                    )

                return evolution_prs

            except ImportError:
                self.logger.warning("requests library not available - cannot check PRs")
                return []
            except Exception as e:
                self.logger.warning(f"Error calling GitHub API: {e}")
                return []

        except Exception as e:
            self.logger.error(f"Error checking open PRs: {e}", exc_info=True)
            return []

    def _poll_github_issues(self) -> int:
        """
        Poll GitHub for approved issues and create tasks for them

        Returns:
            Number of tasks created from approved issues
        """
        try:
            # Get git remote to determine GitHub repo
            cf_root = Path(__file__).parent.parent.parent
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                capture_output=True,
                text=True,
                cwd=str(cf_root),
                timeout=5
            )

            if result.returncode != 0:
                self.logger.debug("Could not get git remote URL")
                return 0

            remote_url = result.stdout.strip()

            # Parse GitHub owner/repo from remote URL
            if 'github.com' in remote_url:
                if remote_url.startswith('git@github.com:'):
                    repo_path = remote_url.replace('git@github.com:', '').replace('.git', '')
                elif 'https://github.com/' in remote_url:
                    repo_path = remote_url.replace('https://github.com/', '').replace('.git', '')
                else:
                    self.logger.debug(f"Unrecognized GitHub URL format: {remote_url}")
                    return 0

                owner, repo = repo_path.split('/')
            else:
                self.logger.debug("Not a GitHub repository")
                return 0

            # Call GitHub API to get issues with "approved" label
            api_url = f'https://api.github.com/repos/{owner}/{repo}/issues'
            params = {'state': 'open', 'labels': 'approved'}

            try:
                import requests

                # Get GitHub token for authentication
                github_token = os.environ.get('GITHUB_TOKEN')

                if not github_token:
                    try:
                        result = subprocess.run(
                            ['gh', 'auth', 'token'],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            github_token = result.stdout.strip()
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        pass

                if not github_token:
                    github_token = self.config.get('github', {}).get('token')

                headers = {}
                if github_token:
                    headers['Authorization'] = f'token {github_token}'

                response = requests.get(api_url, params=params, headers=headers, timeout=10)

                if response.status_code == 403 and 'rate limit' in response.text.lower():
                    self.logger.warning("GitHub API rate limit exceeded. Skipping issue poll.")
                    return 0

                response.raise_for_status()
                issues = response.json()

                if not issues:
                    return 0

                # Check which issues already have tasks in the queue
                existing_tasks = self.task_queue.list_tasks(status=TaskStatus.PENDING.value, limit=100)
                existing_tasks.extend(self.task_queue.list_tasks(status=TaskStatus.RUNNING.value, limit=100))

                existing_issue_nums = set()
                for task in existing_tasks:
                    if 'github_issue' in task.params:
                        existing_issue_nums.add(task.params['github_issue'])

                # Create tasks for new approved issues
                tasks_created = 0
                for issue in issues:
                    issue_number = issue.get('number')
                    issue_title = issue.get('title', 'N/A')
                    issue_body = issue.get('body', '')

                    # Skip if we already have a task for this issue
                    if issue_number in existing_issue_nums:
                        continue

                    # Create task for this approved issue
                    task_id = self.task_queue.create_task(
                        task_type=TaskType.SELF_IMPROVEMENT.value,
                        params={
                            'action': 'implement_github_issue',
                            'github_issue': issue_number,
                            'description': issue_title,
                            'details': issue_body,
                            'priority': 10,  # GitHub-approved issues get highest priority
                            'category': 'github_approved'
                        },
                        priority=10
                    )

                    self.logger.info(f"📋 Created task for approved GitHub issue #{issue_number}: {issue_title}")
                    tasks_created += 1

                if tasks_created > 0:
                    self.logger.info(f"✅ Created {tasks_created} task(s) from approved GitHub issues")

                return tasks_created

            except ImportError:
                self.logger.debug("requests library not available - cannot check issues")
                return 0
            except Exception as e:
                self.logger.debug(f"Error calling GitHub API for issues: {e}")
                return 0

        except Exception as e:
            self.logger.debug(f"Error polling GitHub issues: {e}")
            return 0

    def _check_recently_closed_prs(self):
        """
        Check for recently closed/merged Evolution PRs (last 2 hours)

        This prevents stuck RUNNING tasks when a PR is merged between poll cycles.
        Returns list of closed Evolution PRs.
        """
        try:
            import subprocess
            import json
            from datetime import datetime, timedelta

            # Use gh CLI to get recently closed PRs
            # gh pr list --state closed --limit 20 gives us recent closed PRs
            result = subprocess.run(
                ['gh', 'pr', 'list', '--state', 'closed', '--limit', '20', '--json',
                 'number,headRefName,closedAt,mergedAt,title,url'],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(Path(__file__).parent.parent.parent)
            )

            if result.returncode != 0:
                return []

            prs = json.loads(result.stdout)
            evolution_prs = []

            # Filter for Evolution PRs closed in last 2 hours
            cutoff_time = datetime.now() - timedelta(hours=2)

            evolution_branch_patterns = ['self-improvement/', 'enhancement/', 'fix/']

            for pr in prs:
                branch = pr.get('headRefName', '')
                closed_at = pr.get('closedAt', '')

                # Check if Evolution PR
                is_evolution_pr = any(
                    pattern in branch
                    for pattern in evolution_branch_patterns
                )

                if not is_evolution_pr:
                    continue

                # Check if closed recently (last 2 hours)
                if closed_at:
                    try:
                        # Parse ISO timestamp
                        closed_time = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
                        if closed_time.replace(tzinfo=None) < cutoff_time:
                            continue  # Too old, skip
                    except:
                        pass  # If parsing fails, include it anyway

                # Add to list (will be used to mark RUNNING tasks as COMPLETED)
                pr_dict = {
                    'number': pr.get('number'),
                    'head': {'ref': branch},
                    'html_url': pr.get('url'),
                    'state': 'closed',
                    'merged': pr.get('mergedAt') is not None
                }
                evolution_prs.append(pr_dict)

                self.logger.debug(
                    f"Found recently closed Evolution PR #{pr_dict['number']}: {branch}"
                )

            return evolution_prs

        except Exception as e:
            self.logger.error(f"Error checking recently closed PRs: {e}", exc_info=True)
            return []

    def _check_mcp_status(self):
        """
        Check MCP delegation status for running tasks and log progress

        Monitors MCP tasks via get_delegation_result() and logs phase/status updates
        """
        try:
            from tools.mcp_server import get_delegation_result
            import json

            running_tasks = self.task_queue.list_tasks(status=TaskStatus.RUNNING.value)

            for task in running_tasks:
                if not task.result:
                    continue

                mcp_task_id = task.result.get('mcp_task_id')
                if not mcp_task_id:
                    continue

                # Get MCP status
                try:
                    status_json = get_delegation_result(mcp_task_id, include_full_output=False)
                    status = json.loads(status_json)

                    task_status = status.get('status', 'unknown')
                    current_phase = status.get('current_phase', 'N/A')
                    progress = status.get('progress', 'N/A')

                    # Log MCP progress (only if changed)
                    status_key = f"mcp_{mcp_task_id}_status"
                    last_status = getattr(self, status_key, None)
                    current_status_str = f"{task_status}:{current_phase}"

                    if last_status != current_status_str:
                        self.logger.info(f"🔍 MCP Task {mcp_task_id[:8]} ({task.id[:8]}):")
                        self.logger.info(f"   Status: {task_status}")
                        self.logger.info(f"   Phase: {current_phase}")
                        self.logger.info(f"   Progress: {progress}")
                        setattr(self, status_key, current_status_str)

                except Exception as e:
                    self.logger.debug(f"Could not get MCP status for {mcp_task_id}: {e}")

        except Exception as e:
            self.logger.error(f"Error checking MCP status: {e}", exc_info=True)

    def _detect_prs_and_complete_tasks(self):
        """
        Detect PRs created by Claude and mark corresponding tasks as COMPLETED

        This is the second half of the race condition fix:
        1. Tasks are kept in RUNNING state when Claude is spawned
        2. This method detects when PRs are created and marks tasks COMPLETED
        3. Only then can daemon pick up next task

        Branch naming pattern: self-improvement/task-{task_id[:8]}

        BUG FIX: Also checks recently CLOSED/MERGED PRs to handle the case where
        a PR was merged between poll cycles, preventing stuck RUNNING tasks.
        """
        try:
            # Get all RUNNING tasks first
            running_tasks = self.task_queue.list_tasks(status=TaskStatus.RUNNING.value)
            if not running_tasks:
                return

            # Get all open Evolution PRs
            open_prs = self._check_open_prs()

            # ALSO get recently closed PRs (last 2 hours) to catch merged PRs
            closed_prs = self._check_recently_closed_prs()

            # Combine both lists
            all_prs = open_prs + closed_prs

            if not all_prs:
                return

            # Match PRs to tasks by extracting task ID from branch name
            for pr in all_prs:
                branch = pr.get('head', {}).get('ref', '')
                pr_number = pr.get('number', '?')
                pr_url = pr.get('html_url', '')
                pr_state = pr.get('state', 'unknown')

                # Extract task ID from branch name (e.g., "self-improvement/task-af23b3bd")
                # Branch pattern: {prefix}/task-{task_id[:8]}
                for task in running_tasks:
                    task_id_short = task.id[:8]
                    expected_branch = task.params.get('expected_branch', f"self-improvement/task-{task_id_short}")

                    # EXACT branch match (not substring!) to prevent mismatches
                    if branch != expected_branch:
                        # Log mismatch if task ID appears in branch but doesn't match exactly
                        if f"task-{task_id_short}" in branch:
                            self.logger.warning(f"⚠️  Branch mismatch for task {task.id}:")
                            self.logger.warning(f"   Expected: {expected_branch}")
                            self.logger.warning(f"   Got: {branch}")
                            self.logger.warning(f"   Skipping task completion - wrong branch!")
                        continue

                    # Found matching PR for this task!
                    if pr_state == 'closed':
                        self.logger.info(f"✅ Detected MERGED PR #{pr_number} for task {task.id}")
                        self.logger.info(f"   Branch: {branch}")
                        self.logger.info(f"   Status: Merged (cleaning up stuck RUNNING task)")

                        # Auto-close the GitHub issue if it exists
                        github_issue = task.params.get('github_issue')
                        if github_issue:
                            self._close_github_issue(github_issue, pr_number)
                    else:
                        self.logger.info(f"✅ Detected PR #{pr_number} for task {task.id}")
                        self.logger.info(f"   Branch: {branch}")
                        self.logger.info(f"   URL: {pr_url}")

                    # Mark task as COMPLETED (for both merged and open PRs)
                    result = {
                        'status': 'pr_merged' if pr_state == 'closed' else 'pr_created',
                        'pr_number': pr_number,
                        'pr_url': pr_url,
                        'branch': branch
                    }
                    self.task_queue.update_task_status(
                        task.id,
                        TaskStatus.COMPLETED.value,
                        result=result
                    )

                    self.logger.info(f"🎉 Task {task.id} marked COMPLETED - PR #{pr_number} created!")
                    self.logger.info(f"   Daemon can now pick up next task after PR merge")
                    break

        except Exception as e:
            self.logger.error(f"Error detecting PRs and completing tasks: {e}", exc_info=True)

    def _check_stuck_running_tasks(self):
        """
        Check for tasks stuck in RUNNING state for > 2 hours

        Tasks can get stuck if:
        - Claude crashes without creating PR
        - PR is created on wrong branch
        - Daemon misses PR detection

        Mark stuck tasks as FAILED to unblock the queue
        """
        try:
            from datetime import datetime, timedelta

            running_tasks = self.task_queue.list_tasks(status=TaskStatus.RUNNING.value)
            if not running_tasks:
                return

            timeout_hours = 2
            cutoff_time = datetime.now() - timedelta(hours=timeout_hours)

            for task in running_tasks:
                # Parse task started_at timestamp
                if not task.started_at:
                    continue

                try:
                    started_time = datetime.fromisoformat(task.started_at)

                    if started_time < cutoff_time:
                        # Task has been RUNNING for > 2 hours
                        duration_hours = (datetime.now() - started_time).total_seconds() / 3600

                        self.logger.error(f"⚠️  STUCK TASK: {task.id} has been RUNNING for {duration_hours:.1f} hours")
                        self.logger.error(f"   Expected branch: {task.params.get('expected_branch', 'unknown')}")
                        self.logger.error(f"   No matching PR detected - marking as FAILED")

                        # Mark as FAILED
                        self.task_queue.update_task_status(
                            task.id,
                            TaskStatus.FAILED.value,
                            error=f"Task stuck in RUNNING state for {duration_hours:.1f} hours with no matching PR"
                        )

                        self.logger.info(f"✅ Marked stuck task {task.id} as FAILED - queue unblocked")

                except Exception as e:
                    self.logger.warning(f"Error parsing started_at for task {task.id}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error checking stuck running tasks: {e}", exc_info=True)

    def _close_github_issue(self, issue_number: int, pr_number: int) -> bool:
        """
        Close a GitHub issue when its PR is merged

        Args:
            issue_number: GitHub issue number to close
            pr_number: PR number that fixed the issue

        Returns:
            True if issue was closed successfully, False otherwise
        """
        try:
            import subprocess

            self.logger.info(f"🔒 Closing GitHub issue #{issue_number} (fixed by PR #{pr_number})")

            # Close the issue with a comment linking to the PR
            result = subprocess.run(
                ['gh', 'issue', 'close', str(issue_number),
                 '--comment', f'Fixed by PR #{pr_number} 🤖'],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(Path(__file__).parent.parent.parent)
            )

            if result.returncode == 0:
                self.logger.info(f"✅ Successfully closed issue #{issue_number}")
                return True
            else:
                self.logger.warning(f"Failed to close issue #{issue_number}: {result.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Error closing issue #{issue_number}: {e}")
            return False

    def _queue_next_improvement_task(self):
        """
        Queue the next self-improvement task

        Priority order:
        1. Check GitHub for approved issues first (human-approved tasks)
        2. Fall back to TODOs in codebase
        3. Fall back to self-generated improvement tasks

        Called when PRs are merged to continue the perpetual loop
        """
        try:
            self.logger.info("Generating next improvement task...")

            # PRIORITY 1: Check GitHub for approved issues FIRST
            github_tasks_created = self._poll_github_issues()
            if github_tasks_created > 0:
                self.logger.info(f"✅ Queued {github_tasks_created} GitHub-approved issue(s)")
                return  # GitHub tasks created, we're done

            # PRIORITY 2 & 3: Fall back to TODO/self-generated tasks
            # Use self-improvement mode to find next task
            mode = self.modes.get(TaskType.SELF_IMPROVEMENT.value)
            if not mode:
                self.logger.error("Self-improvement mode not found!")
                return

            # Find next TODO or generate improvement task
            todos = mode._find_todos()

            if todos:
                next_todo = todos[0]  # Get highest priority TODO

                task_id = self.task_queue.create_task(
                    task_type=TaskType.SELF_IMPROVEMENT.value,
                    params={
                        'action': next_todo.get('action', 'implement_todo'),
                        'file': next_todo.get('file'),
                        'line': next_todo.get('line'),
                        'description': next_todo.get('text'),
                        'priority': next_todo.get('priority', 7),
                        'category': next_todo.get('category', 'general')
                    },
                    priority=next_todo.get('priority', 7)
                )

                self.logger.info(f"✅ PERPETUAL LOOP: Queued task {task_id}")
                self.logger.info(f"   📋 Next: {next_todo.get('text', 'Unknown')[:80]}...")
                self.logger.info(f"   🏷️  Category: {next_todo.get('category')} | Priority: {next_todo.get('priority')}")

            else:
                self.logger.warning("⚠️  No more tasks found - perpetual loop paused")
                self.logger.info("   Add TODOs/FIXMEs to Context Foundry code to resume")

        except Exception as e:
            self.logger.error(f"❌ Failed to queue next task: {e}", exc_info=True)


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Context Foundry Evolution Daemon')
    parser.add_argument('command', choices=['start', 'stop', 'status'], help='Command to execute')
    parser.add_argument('--config', help='Path to config file')
    parser.add_argument('--foreground', action='store_true', help='Run in foreground (no daemonize)')
    
    args = parser.parse_args()
    
    daemon = EvolutionDaemon(config_path=args.config)
    
    if args.command == 'start':
        daemon.start(daemonize=not args.foreground)
    elif args.command == 'stop':
        if daemon.is_running():
            pid = daemon.get_pid()
            os.kill(pid, signal.SIGTERM)
            print(f"Sent stop signal to daemon (PID: {pid})")
        else:
            print("Daemon is not running")
    elif args.command == 'status':
        if daemon.is_running():
            print(f"Daemon is running (PID: {daemon.get_pid()})")
        else:
            print("Daemon is not running")


if __name__ == '__main__':
    main()
