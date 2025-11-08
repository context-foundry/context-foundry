#!/usr/bin/env python3
"""
Evolution Daemon for CFES
Main service orchestrator running continuously
"""

import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict, Optional

from .task_queue import TaskQueueManager, Task, TaskStatus
from .resource_manager import ResourceManager


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
        
        # State
        self.running = False
        self.stop_requested = False
        self.active_tasks = {}
        self.pid = None
        
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
                    "max_concurrent_tasks": 3,
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
    
    def main_loop(self):
        """Main daemon loop - polls queue every 60 seconds"""
        poll_interval = self.config.get('daemon', {}).get('poll_interval_seconds', 60)
        max_concurrent = self.config.get('daemon', {}).get('max_concurrent_tasks', 3)
        
        while not self.stop_requested:
            try:
                # Check resources
                can_accept, resource_status = self.resource_manager.can_accept_task()
                
                if not can_accept:
                    self.logger.debug(f"Cannot accept tasks: {resource_status}")
                    time.sleep(poll_interval)
                    continue
                
                # Check if we can accept more tasks
                if len(self.active_tasks) >= max_concurrent:
                    self.logger.debug(f"Max concurrent tasks reached ({max_concurrent})")
                    time.sleep(poll_interval)
                    continue
                
                # Get next task
                task = self.task_queue.get_next_task()
                
                if task:
                    self.logger.info(f"Picked up task: {task.id} (type: {task.type})")
                    self._execute_task(task)
                else:
                    self.logger.debug("No pending tasks")
                
                # Sleep before next poll
                time.sleep(poll_interval)
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(poll_interval)
    
    def _execute_task(self, task: Task):
        """
        Execute task (simplified - would normally delegate to modes)
        
        Args:
            task: Task to execute
        """
        try:
            self.logger.info(f"Executing task {task.id} of type {task.type}")
            
            # Track active task
            self.active_tasks[task.id] = task
            
            # Simulate task execution (in real implementation, delegate to mode)
            result = {
                'status': 'success',
                'message': f'Task {task.type} executed',
                'output': task.params
            }
            
            # Update task status
            self.task_queue.update_task_status(
                task.id,
                TaskStatus.COMPLETED.value,
                result=result
            )
            
            self.logger.info(f"Task {task.id} completed successfully")
            
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
