#!/usr/bin/env python3
"""
Metrics Collector Module
Real-time collection orchestrator for build metrics
"""

import subprocess
import threading
import queue
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import json
import time

from .log_parser import LogParser, TokenUsage
from .metrics_db import MetricsDatabase, get_metrics_db
from .cost_calculator import CostCalculator, get_cost_calculator


class MetricsCollector:
    """Real-time metrics collection orchestrator"""

    def __init__(self,
                 db: Optional[MetricsDatabase] = None,
                 calculator: Optional[CostCalculator] = None):
        """
        Initialize metrics collector.

        Args:
            db: MetricsDatabase instance
            calculator: CostCalculator instance
        """
        self.db = db or get_metrics_db()
        self.calculator = calculator or get_cost_calculator()
        self.parser = LogParser()

        self._usage_queue = queue.Queue()
        self._shutdown = threading.Event()

    def collect_from_subprocess(self,
                                process: subprocess.Popen,
                                session_id: str,
                                phase_name: str,
                                model: str = 'claude-sonnet-4',
                                batch_size: int = 10,
                                batch_timeout: float = 5.0):
        """
        Collect metrics from running subprocess in real-time.

        Args:
            process: subprocess.Popen object
            session_id: Build session ID
            phase_name: Current phase name
            model: Model being used
            batch_size: Number of API calls to batch before writing
            batch_timeout: Seconds to wait before flushing partial batch
        """
        # Ensure build exists in database
        build = self.db.get_build(session_id)
        if not build:
            build_id = self.db.create_build(session_id)
        else:
            build_id = build['id']

        # Create phase record
        phase_id = self.db.create_phase(
            build_id,
            phase_name,
            started_at=datetime.now().isoformat()
        )

        # Start background writer thread
        writer_thread = threading.Thread(
            target=self._batch_writer,
            args=(phase_id, model, batch_size, batch_timeout),
            daemon=True
        )
        writer_thread.start()

        # Parse subprocess output
        try:
            for usage in self.parser.parse_subprocess_output(process):
                # Queue for batch writing
                self._usage_queue.put(usage)

                # Update phase totals immediately (for live display)
                self._update_phase_totals(phase_id, usage, model)

        except Exception as e:
            print(f"Error collecting metrics: {e}")
        finally:
            # Signal shutdown and wait for writer to finish
            self._shutdown.set()
            writer_thread.join(timeout=10)

            # Update phase completion
            self.db.update_phase(
                phase_id,
                completed_at=datetime.now().isoformat()
            )

    def _batch_writer(self, phase_id: int, model: str, batch_size: int, timeout: float):
        """Background thread for batch writing API calls"""
        batch = []
        last_write = time.time()

        while not self._shutdown.is_set() or not self._usage_queue.empty():
            try:
                # Get usage from queue (with timeout)
                usage = self._usage_queue.get(timeout=0.5)
                batch.append(usage)

                # Write batch if full or timeout reached
                if len(batch) >= batch_size or (time.time() - last_write) > timeout:
                    self._write_batch(phase_id, batch, model)
                    batch = []
                    last_write = time.time()

            except queue.Empty:
                # Timeout - check if we should flush partial batch
                if batch and (time.time() - last_write) > timeout:
                    self._write_batch(phase_id, batch, model)
                    batch = []
                    last_write = time.time()

        # Write remaining items
        if batch:
            self._write_batch(phase_id, batch, model)

    def _write_batch(self, phase_id: int, usages: list[TokenUsage], model: str):
        """Write batch of API calls to database"""
        for usage in usages:
            cost = self.calculator.calculate_cost(usage, model)

            self.db.record_api_call(
                phase_id=phase_id,
                model=model,
                tokens_input=usage.input_tokens,
                tokens_output=usage.output_tokens,
                tokens_cached=usage.cache_read_tokens,
                cost=cost,
                latency_ms=None,  # TODO: Calculate from timestamps
                request_id=usage.request_id
            )

    def _update_phase_totals(self, phase_id: int, usage: TokenUsage, model: str):
        """Update phase totals with new usage (for real-time display)"""
        # Note: This is a simplified update. In production, you'd query current
        # totals and increment them
        cost = self.calculator.calculate_cost(usage, model)

        # This will be aggregated from api_calls table, so we don't update here
        # The database queries will calculate totals dynamically
        pass

    def collect_from_phase_file(self, phase_file: Path, session_id: str) -> Dict[str, Any]:
        """
        Collect metrics from .context-foundry/current-phase.json.

        Args:
            phase_file: Path to current-phase.json
            session_id: Session ID

        Returns:
            Dict with collected metrics
        """
        try:
            with open(phase_file, 'r') as f:
                phase_data = json.load(f)

            # Ensure build exists
            build = self.db.get_build(session_id)
            if not build:
                build_id = self.db.create_build(
                    session_id,
                    status=phase_data.get('status', 'running')
                )
            else:
                build_id = build['id']
                # Update status
                self.db.update_build(
                    session_id,
                    status=phase_data.get('status', 'running')
                )

            # Get phase info
            phase_name = phase_data.get('current_phase', 'Unknown')
            phase_number = phase_data.get('phase_number', '?/7')

            return {
                'session_id': session_id,
                'build_id': build_id,
                'phase_name': phase_name,
                'phase_number': phase_number,
                'status': phase_data.get('status', 'running'),
                'phases_completed': phase_data.get('phases_completed', [])
            }

        except (FileNotFoundError, json.JSONDecodeError) as e:
            return {
                'error': str(e),
                'session_id': session_id
            }

    def collect_from_log_file(self, log_file: Path, session_id: str,
                              phase_name: str, model: str = 'claude-sonnet-4'):
        """
        Collect metrics from existing log file.

        Args:
            log_file: Path to log file
            session_id: Session ID
            phase_name: Phase name
            model: Model used
        """
        # Ensure build exists
        build = self.db.get_build(session_id)
        if not build:
            build_id = self.db.create_build(session_id)
        else:
            build_id = build['id']

        # Create phase
        phase_id = self.db.create_phase(
            build_id,
            phase_name,
            started_at=datetime.now().isoformat()
        )

        # Parse log file
        total_cost = 0.0
        total_input = 0
        total_output = 0
        total_cached = 0

        for usage in self.parser.parse_log_file(str(log_file)):
            cost = self.calculator.calculate_cost(usage, model)

            self.db.record_api_call(
                phase_id=phase_id,
                model=model,
                tokens_input=usage.input_tokens,
                tokens_output=usage.output_tokens,
                tokens_cached=usage.cache_read_tokens,
                cost=cost,
                request_id=usage.request_id
            )

            total_cost += cost
            total_input += usage.input_tokens
            total_output += usage.output_tokens
            total_cached += usage.cache_read_tokens

        # Update phase totals
        self.db.update_phase(
            phase_id,
            tokens_input=total_input,
            tokens_output=total_output,
            tokens_cached=total_cached,
            cost=total_cost,
            completed_at=datetime.now().isoformat()
        )

    def finalize_build(self, session_id: str, status: str = 'completed'):
        """
        Finalize build metrics.

        Args:
            session_id: Session ID
            status: Final status
        """
        build = self.db.get_build(session_id)
        if not build:
            return

        # Get aggregated metrics from phases
        metrics = self.db.get_build_metrics(session_id)

        # Update build record
        self.db.update_build(
            session_id,
            status=status,
            total_tokens_input=metrics['total_tokens_input'],
            total_tokens_output=metrics['total_tokens_output'],
            total_tokens_cached=metrics['total_tokens_cached'],
            total_cost=metrics['total_cost'],
            completed_at=datetime.now().isoformat()
        )

        # Check budget alerts
        alerts = self.calculator.get_budget_status(self.db).get('alerts', [])
        for alert in alerts:
            print(alert)

    def start_monitoring(self, working_directory: str):
        """
        Start filesystem watcher for live updates.

        Args:
            working_directory: Directory to monitor
        """
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class PhaseFileHandler(FileSystemEventHandler):
            def __init__(self, collector: MetricsCollector):
                self.collector = collector

            def on_modified(self, event):
                if event.src_path.endswith('current-phase.json'):
                    # Extract session ID from path
                    path = Path(event.src_path)
                    session_id = path.parent.parent.name

                    # Collect metrics
                    self.collector.collect_from_phase_file(path, session_id)

        observer = Observer()
        handler = PhaseFileHandler(self)

        cf_dir = Path(working_directory) / '.context-foundry'
        if cf_dir.exists():
            observer.schedule(handler, str(cf_dir), recursive=False)
            observer.start()

        return observer


def collect_metrics_for_build(working_directory: str, session_id: str):
    """
    Utility function to collect metrics for a completed build.

    Args:
        working_directory: Build working directory
        session_id: Session ID
    """
    collector = MetricsCollector()

    # Look for log files in .context-foundry/
    cf_dir = Path(working_directory) / '.context-foundry'

    if not cf_dir.exists():
        return

    # Parse phase files to determine what was built
    phase_file = cf_dir / 'current-phase.json'
    if phase_file.exists():
        collector.collect_from_phase_file(phase_file, session_id)

    # Look for build logs
    for log_file in cf_dir.glob('*.log'):
        # Try to extract phase from filename
        phase_name = log_file.stem.replace('-', ' ').title()
        collector.collect_from_log_file(log_file, session_id, phase_name)

    # Finalize
    collector.finalize_build(session_id)
