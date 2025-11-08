#!/usr/bin/env python3
"""
Evolution Daemon for CFES
Main service orchestrator running continuously
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from .task_queue import TaskQueueManager, Task, TaskStatus, TaskType
from .resource_manager import ResourceManager
from .modes.self_improvement import SelfImprovementMode
from .modes.chaos_creative import ChaosCreativeMode
from .modes.research_discovery import ResearchDiscoveryMode


# Setup logging
def setup_logging(log_dir: Path):
    """Setup rotating file logging"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "daemon.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
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
        
        self.logger.info(f"Starting Evolution Daemon (PID: {self.pid})")
        self.running = True
        
        try:
            self.main_loop()
        except Exception as e:
            self.logger.error(f"Fatal error in main loop: {e}", exc_info=True)
        finally:
            self.cleanup()
        
        return True
    
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

                # Check resources
                can_accept, resource_status = self.resource_manager.can_accept_task()

                if not can_accept:
                    self.logger.debug(f"Cannot accept tasks: {resource_status}")
                    self._interruptible_sleep(poll_interval)
                    continue

                # Check if we can accept more tasks
                if len(self.active_tasks) >= max_concurrent:
                    self.logger.debug(f"Max concurrent tasks reached ({max_concurrent})")
                    time.sleep(poll_interval)
                    continue

                # RACE CONDITION FIX: Detect PRs created by Claude and mark tasks as COMPLETED
                # This allows daemon to pick up next task after PR is created
                self._detect_prs_and_complete_tasks()

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

                # RACE CONDITION FIX: For self_improvement tasks that spawn Claude,
                # keep them in RUNNING state until PR is created (don't mark COMPLETED)
                # This prevents daemon from picking up another task before PR is created
                if task.type == 'self_improvement' and result.get('output', {}).get('status') == 'claude_spawned':
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

    def _detect_prs_and_complete_tasks(self):
        """
        Detect PRs created by Claude and mark corresponding tasks as COMPLETED

        This is the second half of the race condition fix:
        1. Tasks are kept in RUNNING state when Claude is spawned
        2. This method detects when PRs are created and marks tasks COMPLETED
        3. Only then can daemon pick up next task

        Branch naming pattern: self-improvement/task-{task_id[:8]}
        """
        try:
            # Get all open Evolution PRs
            open_prs = self._check_open_prs()
            if not open_prs:
                return

            # Get all RUNNING tasks
            running_tasks = self.task_queue.list_tasks(status=TaskStatus.RUNNING.value)
            if not running_tasks:
                return

            # Match PRs to tasks by extracting task ID from branch name
            for pr in open_prs:
                branch = pr.get('head', {}).get('ref', '')
                pr_number = pr.get('number', '?')
                pr_url = pr.get('html_url', '')

                # Extract task ID from branch name (e.g., "self-improvement/task-af23b3bd")
                # Branch pattern: {prefix}/task-{task_id[:8]}
                for task in running_tasks:
                    task_id_short = task.id[:8]
                    if f"task-{task_id_short}" in branch:
                        # Found matching PR for this task!
                        self.logger.info(f"✅ Detected PR #{pr_number} for task {task.id}")
                        self.logger.info(f"   Branch: {branch}")
                        self.logger.info(f"   URL: {pr_url}")

                        # Mark task as COMPLETED
                        result = {
                            'status': 'pr_created',
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

    def _queue_next_improvement_task(self):
        """
        Queue the next self-improvement task

        Called when PRs are merged to continue the perpetual loop
        """
        try:
            self.logger.info("Generating next improvement task...")

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
