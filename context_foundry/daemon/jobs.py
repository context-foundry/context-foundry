"""
Job Manager for Context Foundry Daemon

Manages job lifecycle: submission, execution, cancellation, and monitoring.
"""

import logging
import threading
import time
from datetime import datetime
from typing import List, Optional, Dict, Any, Callable
from queue import Queue, Empty

from .models import Job, JobStatus, JobType, LogEntry
from .config import Config
from .store import Store
from .workdir_lock import WorkDirLockManager


logger = logging.getLogger(__name__)


class JobManager:
    """
    Manages Context Foundry Daemon jobs

    Responsibilities:
    - Accept job submissions
    - Queue jobs for execution
    - Execute jobs via Runner
    - Track job status and results
    - Handle retries and failures
    - Provide job query interface
    """

    def __init__(
        self,
        config: Config,
        store: Store,
        runner: Optional[Callable] = None,
    ):
        """
        Initialize JobManager

        Args:
            config: CF Daemon configuration
            store: Store instance for persistence
            runner: Callable that executes jobs (signature: runner(job, store) -> result)
        """
        self.config = config
        self.store = store
        self.runner = runner

        # Worker thread management
        self._workers: List[threading.Thread] = []
        self._stop_event = threading.Event()
        self._running = False

        # Job queue for communication between threads
        self._job_queue: Queue = Queue()

        # Track currently running jobs (job_id -> thread)
        self._running_jobs: Dict[str, threading.Thread] = {}
        self._running_jobs_lock = threading.Lock()

        # Working directory lock manager
        self._workdir_lock = WorkDirLockManager()

        logger.info("JobManager initialized")

    # ===== Job Submission =====

    def submit_job(
        self,
        job_type: JobType,
        params: Dict[str, Any],
        priority: int = 5,
        max_retries: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Job:
        """
        Submit a new job for execution

        Args:
            job_type: Type of job to create
            params: Job-specific parameters
            priority: Job priority (1-10, default 5)
            max_retries: Maximum retry attempts (default from config)
            metadata: Optional metadata dictionary

        Returns:
            Created Job instance
        """
        # Use config default if not specified
        if max_retries is None:
            max_retries = self.config.default_max_retries

        # Create job
        job = Job.create(
            job_type=job_type,
            params=params,
            priority=priority,
            max_retries=max_retries,
            metadata=metadata,
        )

        # Persist to database
        self.store.save_job(job)

        # Emit log
        log = LogEntry.create(
            job_id=job.id,
            level="INFO",
            message=f"Job submitted: {job_type.value}",
            source="job_manager",
        )
        self.store.save_log(log)

        logger.info(
            f"Job submitted: {job.id} (type={job_type.value}, priority={priority})"
        )

        # Wake up workers if running
        if self._running:
            self._job_queue.put(job.id)

        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get job by ID

        Args:
            job_id: Job ID to retrieve

        Returns:
            Job instance or None if not found
        """
        return self.store.get_job(job_id)

    def list_jobs(
        self,
        status: Optional[JobStatus] = None,
        job_type: Optional[JobType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Job]:
        """
        List jobs with optional filters

        Args:
            status: Filter by job status
            job_type: Filter by job type
            limit: Maximum number of jobs to return
            offset: Number of jobs to skip

        Returns:
            List of Job instances
        """
        return self.store.list_jobs(
            status=status,
            job_type=job_type,
            limit=limit,
            offset=offset,
        )

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a job

        Args:
            job_id: Job ID to cancel

        Returns:
            True if job was cancelled, False if job not found or already terminal
        """
        job = self.store.get_job(job_id)
        if not job:
            logger.warning(f"Cannot cancel job {job_id}: not found")
            return False

        # Can only cancel queued or running jobs
        if job.status in [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED]:
            logger.warning(
                f"Cannot cancel job {job_id}: already in terminal state {job.status}"
            )
            return False

        # Update status to CANCELLED
        self.store.update_job_status(
            job_id,
            JobStatus.CANCELLED,
            completed_at=datetime.now(),
        )

        # Emit log
        log = LogEntry.create(
            job_id=job_id,
            level="WARNING",
            message="Job cancelled by user",
            source="job_manager",
        )
        self.store.save_log(log)

        logger.info(f"Job cancelled: {job_id}")
        return True

    # ===== Worker Loop Management =====

    def _get_potentially_locked_directories(self) -> List[str]:
        """
        Get working directories from jobs that might have lockfiles

        Called on daemon startup to find directories that need stale lock cleanup.

        Returns:
            List of working directory paths
        """
        workdirs = []

        # Check RUNNING jobs (may have crashed with locks still held)
        running_jobs = self.store.list_jobs(status=JobStatus.RUNNING, limit=1000)
        for job in running_jobs:
            workdir = job.params.get("working_directory")
            if workdir:
                workdirs.append(workdir)

        # Also check recent FAILED jobs (may have left stale locks)
        failed_jobs = self.store.list_jobs(status=JobStatus.FAILED, limit=100)
        for job in failed_jobs:
            workdir = job.params.get("working_directory")
            if workdir:
                workdirs.append(workdir)

        # Deduplicate
        unique_workdirs = list(set(workdirs))

        logger.info(
            f"Found {len(unique_workdirs)} working directories to check for stale locks"
        )
        return unique_workdirs

    def start(self, num_workers: Optional[int] = None):
        """
        Start job processing workers

        Args:
            num_workers: Number of worker threads (default from config)
        """
        if self._running:
            logger.warning("JobManager already running")
            return

        if num_workers is None:
            num_workers = self.config.max_concurrent_jobs

        self._running = True
        self._stop_event.clear()

        # Clean up stale working directory locks
        # Get working directories from jobs that might have left lockfiles
        logger.info("Cleaning up stale working directory locks...")
        workdirs_to_check = self._get_potentially_locked_directories()
        self._workdir_lock.cleanup_stale_locks(workdirs_to_check)

        # Start worker threads
        for i in range(num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"CFDWorker-{i}",
                daemon=True,
            )
            worker.start()
            self._workers.append(worker)

        logger.info(f"JobManager started with {num_workers} workers")

    def stop(self, timeout: float = 30.0):
        """
        Stop job processing workers

        Args:
            timeout: Maximum time to wait for workers to finish (seconds)
        """
        if not self._running:
            logger.warning("JobManager not running")
            return

        logger.info("Stopping JobManager...")
        self._running = False
        self._stop_event.set()

        # Wake up all workers
        for _ in self._workers:
            self._job_queue.put(None)

        # Wait for workers to finish
        start_time = time.time()
        for worker in self._workers:
            remaining = timeout - (time.time() - start_time)
            if remaining > 0:
                worker.join(timeout=remaining)

        self._workers.clear()
        logger.info("JobManager stopped")

    def is_running(self) -> bool:
        """Check if JobManager is running"""
        return self._running

    def _worker_loop(self):
        """
        Worker loop: picks up queued jobs and executes them

        Runs in a background thread. Continuously polls for QUEUED jobs
        and executes them via the runner.
        """
        logger.info(f"Worker started: {threading.current_thread().name}")

        while not self._stop_event.is_set():
            try:
                # Try to get job ID from queue (with short timeout for responsiveness)
                try:
                    job_id = self._job_queue.get(timeout=0.5)
                    if job_id is None:  # Shutdown signal
                        break
                except Empty:
                    # No jobs in queue, poll database for QUEUED jobs
                    job_id = self._poll_for_job()
                    if job_id is None:
                        # No jobs found, sleep briefly to avoid busy-waiting
                        time.sleep(1.0)
                        continue

                # Execute the job
                self._execute_job(job_id)

            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)

        logger.info(f"Worker stopped: {threading.current_thread().name}")

    def _poll_for_job(self) -> Optional[str]:
        """
        Poll database for next QUEUED job

        Returns:
            Job ID if found, None otherwise
        """
        # Get next queued job (highest priority first)
        jobs = self.store.list_jobs(status=JobStatus.QUEUED, limit=1)
        if not jobs:
            return None

        job = jobs[0]

        # Check if job is already being processed by another worker
        with self._running_jobs_lock:
            if job.id in self._running_jobs:
                return None

            # Claim the job
            self._running_jobs[job.id] = threading.current_thread()

        return job.id

    def _execute_job(self, job_id: str):
        """
        Execute a single job

        Args:
            job_id: Job ID to execute
        """
        working_dir = None
        lock_acquired = False

        try:
            # Retrieve job
            job = self.store.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found")
                return

            # Skip if not queued (might have been cancelled)
            if job.status != JobStatus.QUEUED:
                logger.info(f"Job {job_id} skipped (status={job.status})")
                return

            # Extract working directory from job params (if applicable)
            working_dir = job.params.get("working_directory")

            # Acquire working directory lock (if job has a working directory)
            if working_dir:
                lock_acquired = self._workdir_lock.acquire(working_dir, job_id)

                if not lock_acquired:
                    # Directory is locked by another job - fail this job
                    is_locked, holder_job_id = self._workdir_lock.is_locked(working_dir)
                    error_msg = (
                        f"Working directory {working_dir} is already locked by job {holder_job_id}. "
                        "Cannot execute concurrent builds in the same directory."
                    )
                    logger.warning(error_msg)

                    # Mark job as failed
                    self.store.update_job_status(
                        job_id,
                        JobStatus.FAILED,
                        completed_at=datetime.now(),
                        result={"error": error_msg},
                    )

                    # Emit log
                    log = LogEntry.create(
                        job_id=job_id,
                        level="ERROR",
                        message=error_msg,
                        source="job_manager",
                    )
                    self.store.save_log(log)
                    return

            # Update status to RUNNING
            self.store.update_job_status(
                job_id,
                JobStatus.RUNNING,
                started_at=datetime.now(),
            )

            # Emit log
            log = LogEntry.create(
                job_id=job_id,
                level="INFO",
                message=f"Job execution started: {job.type.value}",
                source="job_manager",
            )
            self.store.save_log(log)

            logger.info(f"Executing job {job_id} (type={job.type.value})")

            # Execute via runner with timeout enforcement
            if self.runner is None:
                raise RuntimeError("No runner configured for JobManager")

            # Get timeout from job params (default to 120 minutes)
            timeout_minutes = job.params.get("timeout_minutes", 120)
            timeout_seconds = timeout_minutes * 60

            # Execute runner in a thread with timeout
            import queue

            result_queue = queue.Queue()
            error_queue = queue.Queue()

            def runner_thread():
                try:
                    result = self.runner(job, self.store)
                    result_queue.put(result)
                except Exception as e:
                    error_queue.put(e)

            thread = threading.Thread(target=runner_thread, name=f"Runner-{job_id}")
            thread.daemon = True
            thread.start()

            # Wait for result with timeout
            thread.join(timeout=timeout_seconds)

            if thread.is_alive():
                # Thread still running - timeout exceeded
                logger.error(
                    f"Job {job_id} exceeded timeout of {timeout_minutes} minutes"
                )
                # Note: Can't forcefully kill the thread, but it's daemon so it will die when process exits
                # The worker will be freed to process other jobs
                raise RuntimeError(
                    f"Job execution exceeded timeout of {timeout_minutes} minutes"
                )

            # Check if error occurred
            if not error_queue.empty():
                raise error_queue.get()

            # Get result
            if not result_queue.empty():
                result = result_queue.get()
            else:
                raise RuntimeError("Job execution completed but no result returned")

            # Mark as succeeded
            self.store.update_job_status(
                job_id,
                JobStatus.SUCCEEDED,
                completed_at=datetime.now(),
                result=result,
            )

            # Emit log
            log = LogEntry.create(
                job_id=job_id,
                level="INFO",
                message="Job completed successfully",
                source="job_manager",
            )
            self.store.save_log(log)

            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            error_msg = f"Job execution failed: {str(e)}"
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)

            # Retrieve job again to get current retry count
            job = self.store.get_job(job_id)
            if not job:
                return

            # Check if we should retry
            if job.retry_count < job.max_retries:
                # Increment retry count and requeue
                new_retry_count = self.store.increment_retry_count(job_id)

                self.store.update_job_status(
                    job_id,
                    JobStatus.QUEUED,  # Requeue for retry
                )

                # Emit log
                log = LogEntry.create(
                    job_id=job_id,
                    level="WARNING",
                    message=f"Job failed, retry {new_retry_count}/{job.max_retries}: {error_msg}",
                    source="job_manager",
                )
                self.store.save_log(log)

                logger.warning(
                    f"Job {job_id} will be retried ({new_retry_count}/{job.max_retries})"
                )

                # Re-enqueue
                if self._running:
                    self._job_queue.put(job_id)

            else:
                # Max retries exceeded, mark as failed
                self.store.update_job_status(
                    job_id,
                    JobStatus.FAILED,
                    completed_at=datetime.now(),
                    error=error_msg,
                )

                # Emit log
                log = LogEntry.create(
                    job_id=job_id,
                    level="ERROR",
                    message=f"Job failed permanently after {job.max_retries} retries: {error_msg}",
                    source="job_manager",
                )
                self.store.save_log(log)

                logger.error(f"Job {job_id} failed permanently")

        finally:
            # Release working directory lock
            if working_dir and lock_acquired:
                self._workdir_lock.release(working_dir, job_id)

            # Remove from running jobs
            with self._running_jobs_lock:
                self._running_jobs.pop(job_id, None)

    # ===== Status and Monitoring =====

    def get_stats(self) -> Dict[str, Any]:
        """
        Get JobManager statistics

        Returns:
            Dictionary with various stats
        """
        job_stats = self.store.get_job_stats()

        with self._running_jobs_lock:
            running_count = len(self._running_jobs)
            running_job_ids = list(self._running_jobs.keys())

        return {
            "running": self._running,
            "num_workers": len(self._workers),
            "jobs_running": running_count,
            "running_job_ids": running_job_ids,
            "job_counts": job_stats,
        }

    def get_running_jobs(self) -> List[Job]:
        """
        Get list of currently running jobs

        Returns:
            List of Job instances with RUNNING status
        """
        return self.store.list_jobs(status=JobStatus.RUNNING)
