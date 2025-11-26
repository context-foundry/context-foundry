"""
CF Daemon CLI

Command-line interface for Context Foundry Daemon.
Provides commands for start/stop/status/submit/list/logs/cancel.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

from .config import Config
from .store import Store
from .server import CFDaemon, get_running_daemon_pid, stop_running_daemon
from .models import JobType, JobStatus

# Import pipeline state for pause/resume functionality
try:
    from tools.mcp_utils.pipeline_state import (
        get_pipeline_state,
        can_resume_pipeline,
        PipelineState,
        PHASE_ORDER,
    )

    PIPELINE_STATE_AVAILABLE = True
except ImportError:
    PIPELINE_STATE_AVAILABLE = False


def cmd_start(args):
    """Start the daemon"""
    config = Config.load(args.config)

    # Check if already running
    pid = get_running_daemon_pid(config)
    if pid:
        print(f"Daemon is already running (PID {pid})")
        return 1

    try:
        daemon = CFDaemon(config, config_path=args.config)
        success = daemon.start(foreground=args.foreground)
        return 0 if success else 1
    except Exception as e:
        print(f"Failed to start daemon: {e}", file=sys.stderr)
        return 1


def cmd_stop(args):
    """Stop the daemon"""
    config = Config.load(args.config)

    pid = get_running_daemon_pid(config)
    if not pid:
        print("Daemon is not running")
        return 1

    print(f"Stopping daemon (PID {pid})...")
    success = stop_running_daemon(config, timeout=args.timeout)

    if success:
        print("Daemon stopped")
        return 0
    else:
        print("Failed to stop daemon", file=sys.stderr)
        return 1


def cmd_status(args):
    """Get daemon status"""
    config = Config.load(args.config)

    pid = get_running_daemon_pid(config)
    if not pid:
        print("Daemon is not running")
        return 1

    from .art import get_lava_lamp_art
    import random

    # Use random frame for variety each time status is called
    frame = random.randint(0, 359)
    print(get_lava_lamp_art(frame))
    print(f"Daemon is running (PID {pid})")

    # Check heartbeat health
    heartbeat_file = config.data_dir / "daemon_heartbeat.txt"
    try:
        if heartbeat_file.exists():
            lines = heartbeat_file.read_text().strip().split("\n")
            if len(lines) >= 3:
                last_heartbeat_time = int(lines[0])
                iteration_count = int(lines[1])
                heartbeat_pid = int(lines[2])

                current_time = int(time.time())
                age = current_time - last_heartbeat_time

                if age < 10:
                    health = "✓ Healthy"
                elif age < 60:
                    health = f"⚠ Warning (heartbeat {age}s old)"
                else:
                    health = f"✗ UNHEALTHY (heartbeat {age}s old - daemon may be hung)"

                print(f"Health: {health}")
                if args.verbose:
                    print(f"  Last heartbeat: {age}s ago")
                    print(f"  Loop iterations: {iteration_count}")
                    print(f"  Heartbeat PID: {heartbeat_pid}")
            else:
                print("Health: ⚠ Warning (incomplete heartbeat file)")
        else:
            print("Health: ⚠ Warning (no heartbeat file - may be starting up)")
    except Exception as e:
        print(f"Health: ⚠ Warning (failed to read heartbeat: {e})")

    if args.verbose:
        # Get more detailed status
        store = Store(config.db_path)
        stats = store.get_job_stats()

        print("\nJob Statistics:")
        for status, count in stats.items():
            print(f"  {status}: {count}")

        print("\nConfiguration:")
        print(f"  Data dir: {config.data_dir}")
        print(f"  Log dir: {config.log_dir}")
        print(f"  DB path: {config.db_path}")
        print(f"  Max concurrent jobs: {config.max_concurrent_jobs}")

    # Show ALL related processes (always, not just in verbose mode)
    print("\n═══════════════════════════════════════════════════════════")
    print("ALL RELATED PROCESSES:")
    print("═══════════════════════════════════════════════════════════")

    related_processes = _find_all_related_processes(pid)
    if related_processes:
        for proc in related_processes:
            print(f"  [{proc['type']}] PID {proc['pid']}: {proc['cmd'][:80]}")
        print(f"\nTotal: {len(related_processes)} related processes")
        print("\nTo kill all: cfd killall")
        print("To kill specific: kill <PID>")
    else:
        print("  ✓ No related processes found (only daemon running)")

    # Check for zombie processes
    from .zombies import find_zombies, format_zombie_list, PSUTIL_AVAILABLE

    if PSUTIL_AVAILABLE:
        zombies = find_zombies(exclude_pids=[pid])
        if zombies:
            print("\n⚠️  Zombie Processes Detected:")
            print(format_zombie_list(zombies))
            print("\nRun 'cfd cleanup' to remove these processes")
        elif args.verbose:
            print("\n✓ No zombie processes detected")
    elif args.verbose:
        print("\n⚠️  psutil not available - cannot detect zombie processes")

    return 0


def _find_all_related_processes(daemon_pid):
    """Find all Context Foundry related processes"""
    import subprocess

    related = []

    try:
        # Get all processes
        ps_output = subprocess.check_output(["ps", "aux"], text=True)

        for line in ps_output.splitlines()[1:]:  # Skip header
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue

            pid_str = parts[1]
            cmd = parts[10]

            try:
                proc_pid = int(pid_str)
            except ValueError:
                continue

            # Skip daemon itself
            if proc_pid == daemon_pid:
                continue

            # Categorize process types
            proc_type = None

            # Check for Claude processes (build agents)
            # Match: "claude" command that's running builds
            if cmd.strip().startswith("claude") or "bin/claude" in cmd:
                # Basic claude command - likely a build process
                proc_type = "CLAUDE"
            elif "claude" in cmd.lower() and "context-foundry" in cmd.lower():
                # Claude explicitly working with context-foundry
                proc_type = "CLAUDE"
            elif "tail -f" in cmd and ".context-foundry" in cmd:
                proc_type = "MONITOR"
            elif "grep" in cmd and (
                "architect" in cmd or "baml" in cmd or "o4-mini" in cmd
            ):
                proc_type = "MONITOR"
            elif "mcp_server.py" in cmd:
                proc_type = "MCP"
            elif "cfd" in cmd and ("logs" in cmd or "submit" in cmd):
                proc_type = "CFD-CMD"
            elif "python" in cmd and "build_runner.py" in cmd:
                proc_type = "BUILD"
            elif ".context-foundry" in cmd:
                proc_type = "CF-PROC"

            if proc_type:
                related.append({"pid": proc_pid, "type": proc_type, "cmd": cmd})

    except Exception as e:
        print(f"Warning: Could not enumerate processes: {e}")

    return related


def _restart_daemon(config, config_path, timeout):
    """Stop the current daemon (if running) and start a new instance."""
    print("Attempting daemon restart...")
    stop_running_daemon(config, timeout=timeout)

    try:
        daemon = CFDaemon(config, config_path=config_path)
        started = daemon.start(foreground=False)
        if started:
            print("Daemon restarted")
            return True
        print("Daemon failed to restart", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Daemon restart failed: {e}", file=sys.stderr)
        return False


def cmd_healthcheck(args):
    """Machine-friendly healthcheck for supervisors (optionally restart daemon)"""
    config = Config.load(args.config)
    pid = get_running_daemon_pid(config)

    if not pid:
        print("Daemon is not running")
        if args.restart:
            return 0 if _restart_daemon(config, args.config, args.timeout) else 3
        return 2

    heartbeat_file = config.data_dir / "daemon_heartbeat.txt"
    state = "unknown"
    age = None
    iteration_count = None
    heartbeat_pid = None

    try:
        lines = heartbeat_file.read_text().strip().split("\n")
        if len(lines) >= 3:
            last_heartbeat_time = int(lines[0])
            iteration_count = int(lines[1])
            heartbeat_pid = int(lines[2])
            age = int(time.time()) - last_heartbeat_time

            if age < 10:
                state = "healthy"
            elif age < args.max_stale:
                state = "warning"
            else:
                state = "unhealthy"
        else:
            state = "error"
    except FileNotFoundError:
        state = "missing"
    except Exception as e:
        print(f"Heartbeat read failed: {e}")
        state = "error"

    if state == "healthy":
        print(f"Healthy (age {age}s)")
        return 0

    if state == "warning":
        print(f"Warning: heartbeat is stale (age {age}s)")
        exit_code = 1
    elif state in {"unhealthy", "missing", "error"}:
        detail = f"age {age}s" if age is not None else "no heartbeat available"
        print(f"Unhealthy: {detail}")
        exit_code = 2
    else:
        print("Unhealthy: unknown heartbeat state")
        exit_code = 2

    if args.restart:
        restart_ok = _restart_daemon(config, args.config, args.timeout)
        return 0 if restart_ok else 3

    if args.verbose and iteration_count is not None:
        print(f"  Loop iterations: {iteration_count}")
        print(f"  Heartbeat PID: {heartbeat_pid}")

    return exit_code


def cmd_submit(args):
    """Submit a new job"""
    config = Config.load(args.config)
    store = Store(config.db_path)

    # Check daemon is running
    if not get_running_daemon_pid(config):
        print("Warning: Daemon is not running. Job will be queued but not executed.")

    # Parse job type
    try:
        job_type = JobType(args.type)
    except ValueError:
        print(f"Invalid job type: {args.type}", file=sys.stderr)
        print(f"Valid types: {', '.join(t.value for t in JobType)}", file=sys.stderr)
        return 1

    # Parse parameters
    try:
        params = json.loads(args.params) if args.params else {}
    except json.JSONDecodeError as e:
        print(f"Invalid JSON parameters: {e}", file=sys.stderr)
        return 1

    # Create job via JobManager (just use store directly for now)
    from .jobs import JobManager

    job_manager = JobManager(config, store, runner=None)
    job = job_manager.submit_job(
        job_type=job_type,
        params=params,
        priority=args.priority,
        max_retries=args.max_retries
        if args.max_retries is not None
        else config.default_max_retries,
    )

    print(f"Job submitted: {job.id}")
    print(f"  Type: {job.type.value}")
    print(f"  Priority: {job.priority}")
    print(f"  Status: {job.status.value}")

    if args.wait:
        print("\nWaiting for job to complete...")
        _wait_for_job(store, job.id, args.timeout)

    return 0


def cmd_list(args):
    """List jobs"""
    config = Config.load(args.config)
    store = Store(config.db_path)

    # Parse status filter
    status_filter = None
    if args.status:
        try:
            status_filter = JobStatus(args.status)
        except ValueError:
            print(f"Invalid status: {args.status}", file=sys.stderr)
            print(
                f"Valid statuses: {', '.join(s.value for s in JobStatus)}",
                file=sys.stderr,
            )
            return 1

    # List jobs
    jobs = store.list_jobs(
        status=status_filter,
        limit=args.limit,
        offset=args.offset,
    )

    if not jobs:
        print("No jobs found")
        return 0

    # Print jobs
    print(f"{'ID':<38} {'Type':<20} {'Status':<12} {'Priority':<8} {'Created':<20}")
    print("-" * 100)

    for job in jobs:
        print(
            f"{job.id:<38} {job.type.value:<20} {job.status.value:<12} "
            f"{job.priority:<8} {job.created_at.strftime('%Y-%m-%d %H:%M:%S'):<20}"
        )

    return 0


def cmd_show(args):
    """Show job details"""
    config = Config.load(args.config)
    store = Store(config.db_path)

    job = store.get_job(args.job_id)
    if not job:
        print(f"Job not found: {args.job_id}", file=sys.stderr)
        return 1

    # Print job details
    from .art import get_status_art

    print(get_status_art())
    print(f"Job ID: {job.id}")
    print(f"Type: {job.type.value}")
    print(f"Status: {job.status.value}")
    print(f"Priority: {job.priority}")
    print(f"Created: {job.created_at}")
    print(f"Started: {job.started_at or 'N/A'}")
    print(f"Completed: {job.completed_at or 'N/A'}")
    print(f"Retry count: {job.retry_count}/{job.max_retries}")

    if job.duration():
        print(f"Duration: {job.duration():.2f}s")

    print("\nParameters:")
    print(json.dumps(job.params, indent=2))

    if job.result:
        print("\nResult:")
        print(json.dumps(job.result, indent=2))

    if job.error:
        print("\nError:")
        print(job.error)

    # Show phase events
    phase_events = store.get_phase_events(job.id)
    if phase_events:
        print("\nPhase Events:")
        for event in phase_events:
            print(f"  {event.phase}: {event.status} at {event.timestamp}")

    return 0


def display_phase_breakdown(job, store):
    """Display detailed phase breakdown for a job"""

    # Get phase events for this job
    phase_events = store.get_phase_events(job.id)

    if not phase_events:
        print(f"\nJob: {job.id[:8]} ({job.type.value})")
        print(f"Status: {job.status.value.upper()}")
        print("\n⚠️  No phase information available")
        print("   This build failed before phase tracking started.")
        print("\nShowing error logs instead:\n")

        # Show error logs
        error_logs = store.get_logs(job_id=job.id, level="ERROR", limit=10)
        if error_logs:
            for log in error_logs:
                timestamp = log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                print(f"{timestamp} │ {log.message}")
        else:
            all_logs = store.get_logs(job_id=job.id, limit=10)
            if all_logs:
                print("Last logs:")
                for log in all_logs[-5:]:
                    timestamp = log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    print(f"{timestamp} {log.level:<8} │ {log.message}")
            else:
                print("No logs available")
        return

    # Group events by phase
    phase_data = {}
    for event in phase_events:
        if event.phase not in phase_data:
            phase_data[event.phase] = []
        phase_data[event.phase].append(event)

    # Display job header
    print(f"\nJob: {job.id[:8]} ({job.type.value})")
    print(f"Status: {job.status.value.upper()}", end="")

    if job.duration():
        minutes = int(job.duration() // 60)
        seconds = int(job.duration() % 60)
        print(f" | Duration: {minutes}m {seconds}s")
    else:
        print()

    print("\nPhases:")
    print("=" * 80)

    # Get phases_completed from result if available
    phases_completed = []
    if job.result and isinstance(job.result, dict):
        phases_completed = job.result.get("phases_completed", [])

    # Display each phase
    for phase_name, events in sorted(phase_data.items()):
        # Get latest event for this phase
        latest_event = events[-1]
        status = latest_event.status

        # Override status if phase is in phases_completed (more reliable)
        if phase_name in phases_completed:
            status = "completed"

        # Status icon
        if status == "completed":
            icon = "✓"
        elif status == "failed":
            icon = "✗"
        elif status in ["started", "in_progress"]:
            icon = "⋯"
        else:
            icon = "○"

        # Format phase line
        phase_display = f"  {icon} {phase_name:<12}"
        status_display = f"[{status.upper():<12}]"

        # Add duration if available
        if latest_event.duration_seconds is not None:
            minutes = int(latest_event.duration_seconds // 60)
            seconds = int(latest_event.duration_seconds % 60)
            duration_display = f" {minutes}m {seconds}s"
        else:
            duration_display = ""

        print(f"{phase_display}{status_display}{duration_display}")

        # Show additional details if available
        if latest_event.tokens_used:
            print(f"    └─ Tokens: {latest_event.tokens_used:,}")

        if latest_event.context_percent:
            print(f"    └─ Context: {latest_event.context_percent:.1f}%")

        # Show details dict if it has useful info
        if latest_event.details:
            if "error" in latest_event.details:
                print(f"    └─ Error: {latest_event.details['error']}")
            elif "files_created" in latest_event.details:
                print(f"    └─ Files created: {latest_event.details['files_created']}")
            elif (
                "tests_passed" in latest_event.details
                and "tests_total" in latest_event.details
            ):
                passed = latest_event.details["tests_passed"]
                total = latest_event.details["tests_total"]
                print(f"    └─ Tests: {passed}/{total} passed")

    # Show timeout information
    if job.params and "timeout_minutes" in job.params:
        timeout_minutes = job.params["timeout_minutes"]
        print(f"\n⏱️  Timeout: {timeout_minutes}m total", end="")

        if job.duration():
            elapsed_minutes = job.duration() / 60
            remaining_minutes = timeout_minutes - elapsed_minutes

            if remaining_minutes > 0:
                print(f" | {remaining_minutes:.1f}m remaining")
            else:
                print(" | EXCEEDED")
        else:
            print()

    # Show error logs for failed phases
    failed_phases = [
        phase_name
        for phase_name, events in phase_data.items()
        if events[-1].status == "failed"
    ]

    if failed_phases:
        print("\n" + "=" * 80)
        print("Error Details:")
        print("=" * 80)

        for phase_name in failed_phases:
            # Get logs for this phase
            phase_logs = store.get_logs(job_id=job.id, level="ERROR", limit=20)

            # Filter logs for this phase
            relevant_logs = [log for log in phase_logs if log.phase == phase_name]

            if relevant_logs:
                print(f"\n[{phase_name}] Last errors:")
                for log in relevant_logs[-5:]:  # Last 5 errors
                    timestamp = log.timestamp.strftime("%H:%M:%S")
                    print(f"  {timestamp} │ {log.message}")


def cmd_logs(args):
    """Show job logs"""
    config = Config.load(args.config)
    store = Store(config.db_path)

    job = store.get_job(args.job_id)
    if not job:
        print(f"Job not found: {args.job_id}", file=sys.stderr)
        return 1

    # Show phase breakdown if requested
    if args.phases:
        display_phase_breakdown(job, store)
        return 0

    # Get logs
    logs = store.get_logs(
        job_id=args.job_id,
        level=args.level,
        limit=args.limit if not args.follow else 10000,
    )

    if not logs and not args.follow:
        print("No logs found")
        return 0

    # Print logs
    for log in logs:
        timestamp = log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        phase = f"[{log.phase}]" if log.phase else ""
        print(f"{timestamp} {log.level:<8} {phase:<12} {log.message}")

    # Follow mode
    if args.follow:
        last_log_id = logs[-1].id if logs else None

        try:
            while True:
                time.sleep(1)

                # Get new logs
                all_logs = store.get_logs(job_id=args.job_id, limit=10000)

                # Find logs after last_log_id
                new_logs = []
                found_last = False
                for log in all_logs:
                    if found_last:
                        new_logs.append(log)
                    elif last_log_id and log.id == last_log_id:
                        found_last = True

                if not last_log_id:
                    new_logs = all_logs

                # Print new logs
                for log in new_logs:
                    timestamp = log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    phase = f"[{log.phase}]" if log.phase else ""
                    print(f"{timestamp} {log.level:<8} {phase:<12} {log.message}")

                if new_logs:
                    last_log_id = new_logs[-1].id

                # Check if job completed
                job = store.get_job(args.job_id)
                if job.status in [
                    JobStatus.SUCCEEDED,
                    JobStatus.FAILED,
                    JobStatus.CANCELLED,
                ]:
                    print(f"\nJob completed with status: {job.status.value}")
                    break

        except KeyboardInterrupt:
            print("\nStopped following logs")

    return 0


def cmd_cancel(args):
    """Cancel a job"""
    config = Config.load(args.config)
    store = Store(config.db_path)

    # Use JobManager to cancel (handles status updates and logging)
    from .jobs import JobManager

    job_manager = JobManager(config, store, runner=None)
    success = job_manager.cancel_job(args.job_id)

    if success:
        print(f"Job cancelled: {args.job_id}")
        return 0
    else:
        print(f"Failed to cancel job: {args.job_id}", file=sys.stderr)
        return 1


def cmd_cleanup(args):
    """Clean up zombie processes"""
    from .zombies import (
        find_zombies,
        kill_process,
        format_zombie_list,
        PSUTIL_AVAILABLE,
    )

    if not PSUTIL_AVAILABLE:
        print(
            "Error: psutil is not available. Cannot detect zombie processes.",
            file=sys.stderr,
        )
        print("Install with: pip install psutil", file=sys.stderr)
        return 1

    # Find zombies
    zombies = find_zombies()

    if not zombies:
        print("✓ No zombie processes detected")
        return 0

    # Display zombies
    print("Found zombie processes:")
    print(format_zombie_list(zombies))

    if args.force:
        # Kill all without confirmation
        print("\nKilling all zombie processes (--force mode)...")
        killed = 0
        failed = 0

        for zombie in zombies:
            print(f"Killing PID {zombie.pid} ({zombie.name})...", end=" ")
            if kill_process(zombie.pid, force=True):
                print("✓")
                killed += 1
            else:
                print("✗ Failed")
                failed += 1

        print(f"\nKilled {killed} process(es), {failed} failed")
        return 0 if failed == 0 else 1

    # Interactive mode
    print("\nInteractive cleanup mode. For each process:")
    print("  y = kill this process")
    print("  n = skip this process")
    print("  a = kill all remaining")
    print("  q = quit without killing more\n")

    killed = 0
    skipped = 0

    for i, zombie in enumerate(zombies, 1):
        print(f"\n[{i}/{len(zombies)}] PID {zombie.pid}: {zombie.name}")
        print(f"  Age: {zombie.age_seconds/3600:.1f}h")
        print(f"  Reason: {zombie.reason}")
        print(f"  Command: {zombie.cmdline[:80]}")
        print(f"  Kill command: kill -9 {zombie.pid}")

        while True:
            choice = input("\nAction [y/n/a/q]: ").strip().lower()

            if choice == "y":
                print(f"Killing PID {zombie.pid}...", end=" ")
                if kill_process(zombie.pid, force=True):
                    print("✓")
                    killed += 1
                else:
                    print("✗ Failed")
                break

            elif choice == "n":
                print("Skipped")
                skipped += 1
                break

            elif choice == "a":
                # Kill this one and all remaining
                remaining = zombies[i - 1 :]
                print(f"\nKilling {len(remaining)} remaining process(es)...")

                for z in remaining:
                    print(f"Killing PID {z.pid} ({z.name})...", end=" ")
                    if kill_process(z.pid, force=True):
                        print("✓")
                        killed += 1
                    else:
                        print("✗ Failed")

                print(f"\nKilled {killed} process(es), skipped {skipped}")
                return 0

            elif choice == "q":
                print(
                    f"\nQuitting. Killed {killed} process(es), skipped {skipped + len(zombies) - i}"
                )
                return 0

            else:
                print("Invalid choice. Please enter y, n, a, or q.")

    print(f"\nDone. Killed {killed} process(es), skipped {skipped}")
    return 0


def cmd_killall(args):
    """Kill all Context Foundry related processes except daemon and current process"""
    import os
    import signal

    config = Config.load(args.config)

    # Get daemon PID
    pid = get_running_daemon_pid(config)
    if not pid:
        print("❌ Daemon is not running (no PID file found)")
        return 1

    # Get current process PID (the user's cfd process)
    current_pid = os.getpid()

    # Find all related processes
    print("Scanning for Context Foundry processes...")
    related_processes = _find_all_related_processes(pid)

    if not related_processes:
        print("✓ No related processes found to kill")
        return 0

    # Filter out daemon and current process
    killable = [
        p for p in related_processes if p["pid"] != pid and p["pid"] != current_pid
    ]

    if not killable:
        print("✓ No killable processes found (only daemon running)")
        return 0

    # Show what will be killed
    print(f"\nFound {len(killable)} process(es) to kill:")
    print("═══════════════════════════════════════════════════════════")
    for proc in killable:
        print(f"  [{proc['type']}] PID {proc['pid']}: {proc['cmd'][:60]}")
    print("═══════════════════════════════════════════════════════════")

    # Confirm unless --force
    if not args.force:
        response = input(f"\nKill all {len(killable)} process(es)? [y/N]: ")
        if response.lower() != "y":
            print("Cancelled.")
            return 0

    # Kill all processes
    killed = 0
    failed = 0

    print("\nKilling processes...")
    for proc in killable:
        try:
            os.kill(proc["pid"], signal.SIGTERM)
            print(f"  ✓ Killed PID {proc['pid']} ({proc['type']})")
            killed += 1
        except ProcessLookupError:
            print(f"  ⚠ PID {proc['pid']} already dead")
            killed += 1
        except PermissionError:
            print(f"  ✗ PID {proc['pid']} permission denied")
            failed += 1
        except Exception as e:
            print(f"  ✗ PID {proc['pid']} error: {e}")
            failed += 1

    print(f"\nResults: {killed} killed, {failed} failed")

    if failed > 0:
        print("\nTip: Try running with sudo for permission issues")

    return 0


def cmd_pipeline_status(args):
    """Show pipeline state for a project directory"""
    if not PIPELINE_STATE_AVAILABLE:
        print("Error: Pipeline state module not available", file=sys.stderr)
        return 1

    project_dir = Path(args.dir).resolve()
    if not project_dir.exists():
        print(f"Error: Directory does not exist: {project_dir}", file=sys.stderr)
        return 1

    state = get_pipeline_state(project_dir)
    if not state:
        print(f"No pipeline state found in {project_dir}")
        print("  (No build has been run with pause/resume enabled)")
        return 0

    # Display pipeline state
    print(f"\n{'=' * 60}")
    print(f"Pipeline Status: {project_dir.name}")
    print(f"{'=' * 60}")
    print(state.get_status_summary())

    # Show resume command if applicable
    if state.state in PipelineState.resumable_states():
        print(f"\n{'=' * 60}")
        print("To resume this pipeline:")
        print(f"  cfd resume --dir {project_dir}")
        if state.phases_remaining:
            print(
                f"  cfd resume --dir {project_dir} --from {state.phases_remaining[0]}"
            )
        print(f"{'=' * 60}")

    return 0


def cmd_run_phase(args):
    """Run specific phase(s) with contract validation"""
    # Import phase registry and contracts
    try:
        from tools.mcp_utils.phase_registry import (
            get_registry,
            PHASE_ORDER as REGISTRY_PHASE_ORDER,
        )
        from tools.mcp_utils.contracts import validate_phase_inputs
    except ImportError as e:
        print(f"Error: Phase registry module not available: {e}", file=sys.stderr)
        return 1

    project_dir = Path(args.dir).resolve()
    if not project_dir.exists():
        print(f"Error: Directory does not exist: {project_dir}", file=sys.stderr)
        return 1

    # Parse phase names
    phase_names = args.phases
    if not phase_names:
        print("Error: No phases specified", file=sys.stderr)
        print("Usage: cfd run-phase Scout [Architect Builder ...]", file=sys.stderr)
        return 1

    registry = get_registry()

    # Resolve phase names to PhaseIds
    phases, error = registry.resolve_phase_list(phase_names)
    if error:
        print(f"Error: {error}", file=sys.stderr)
        valid_phases = [p.value for p in REGISTRY_PHASE_ORDER]
        print(f"Valid phases: {', '.join(valid_phases)}", file=sys.stderr)
        return 1

    # If --with-deps flag, include all dependencies
    if args.with_deps:
        phases = registry.get_required_phases_for(phases)
        print(f"Including dependencies: {', '.join(p.value for p in phases)}")

    # Validate input contracts unless --skip-contracts
    if not args.skip_contracts:
        for phase_id in phases:
            phase_def = registry.get_phase(phase_id)
            if phase_def and phase_def.required_inputs:
                result = validate_phase_inputs(
                    phase_def.name, project_dir, phase_def.required_inputs
                )
                if not result.passed:
                    print(f"Error: Input contract failed for {phase_def.name}:")
                    for v in result.violations:
                        print(f"  - {v.message}")
                        if v.suggestion:
                            print(f"    Suggestion: {v.suggestion}")
                    if not args.force:
                        return 1
                    print("Continuing anyway (--force specified)...")

    print(f"Running phases: {', '.join(p.value for p in phases)}")
    print(f"Working directory: {project_dir}")
    print()

    config = Config.load(args.config)

    # Build task config for selective execution
    task_config = {
        "task": f"Run phases: {', '.join(p.value for p in phases)}",
        "working_directory": str(project_dir),
        "mode": "selective",
        "target_phases": [p.value for p in phases],
        "skip_contracts": args.skip_contracts,
        "timeout_minutes": args.timeout or 90,
    }

    # Check if daemon is running
    if not get_running_daemon_pid(config):
        print("Warning: Daemon is not running. Starting phase execution directly...")

        # Import and run directly
        from tools.mcp_utils.autonomous_build import execute_build_with_phase_spawning

        result = execute_build_with_phase_spawning(
            task=task_config["task"],
            working_directory=project_dir,
            task_config=task_config,
            enable_test_loop="Test" in [p.value for p in phases],
            max_test_iterations=3,
            flowise_mode=False,
            project_type="unknown",
            incremental=True,
            use_parallel=None,
            timeout_minutes=task_config["timeout_minutes"],
            target_phases=[p.value for p in phases],
        )

        if result.get("status") == "completed":
            print("\n✅ Phases completed successfully")
            return 0
        else:
            print(f"\n❌ Phases failed: {result.get('error', 'Unknown error')}")
            return 1

    # Submit to daemon
    store = Store(config.db_path)
    from .jobs import JobManager

    job_manager = JobManager(config, store, runner=None)
    job = job_manager.submit_job(
        job_type=JobType.AUTONOMOUS_BUILD,
        params=task_config,
        priority=args.priority,
    )

    print()
    print(f"Job submitted: {job.id}")
    print(f"  Type: {job.type.value}")
    print(f"  Phases: {', '.join(p.value for p in phases)}")
    print(f"  Status: {job.status.value}")
    print()
    print(f"Monitor with: cfd logs {job.id} --phases")

    # If --wait, block until complete
    if args.wait:
        return _wait_for_job(config, job.id, args.timeout)

    return 0


def cmd_resume(args):
    """Resume a paused pipeline"""
    if not PIPELINE_STATE_AVAILABLE:
        print("Error: Pipeline state module not available", file=sys.stderr)
        return 1

    project_dir = Path(args.dir).resolve()
    if not project_dir.exists():
        print(f"Error: Directory does not exist: {project_dir}", file=sys.stderr)
        return 1

    # Check if pipeline can be resumed
    can_resume, reason = can_resume_pipeline(project_dir)
    if not can_resume:
        print(f"Error: Cannot resume pipeline: {reason}", file=sys.stderr)
        return 1

    state = get_pipeline_state(project_dir)
    if not state:
        print("Error: No pipeline state found", file=sys.stderr)
        return 1

    # Determine which phase to resume from
    resume_from = args.from_phase
    if resume_from:
        # Validate phase name
        if resume_from not in PHASE_ORDER:
            print(f"Error: Invalid phase: {resume_from}", file=sys.stderr)
            print(f"Valid phases: {', '.join(PHASE_ORDER)}", file=sys.stderr)
            return 1
    else:
        # Resume from next phase
        resume_from = state.get_next_phase()

    if not resume_from:
        print("Pipeline is already complete - nothing to resume")
        return 0

    print(f"Resuming pipeline from phase: {resume_from}")
    print(f"Phases completed: {', '.join(state.phases_completed) or 'None'}")
    print(f"Phases remaining: {', '.join(state.phases_remaining)}")

    # Get task config from saved state
    task_config = state.task_config
    if not task_config:
        print("Error: No task configuration found in pipeline state", file=sys.stderr)
        return 1

    config = Config.load(args.config)

    # Check daemon is running
    if not get_running_daemon_pid(config):
        print("Warning: Daemon is not running. Starting build directly...")
        # For now, run directly without daemon
        from tools.mcp_utils.autonomous_build import execute_build_with_phase_spawning

        # Extract all required parameters from task_config
        result = execute_build_with_phase_spawning(
            task=task_config.get("task", "Resume build"),
            working_directory=project_dir,
            task_config=task_config,
            enable_test_loop=task_config.get("enable_test_loop", True),
            max_test_iterations=task_config.get("max_test_iterations", 3),
            flowise_mode=task_config.get("flowise_flow", False),
            project_type=task_config.get("project_type", "unknown"),
            incremental=task_config.get("incremental", False),
            use_parallel=task_config.get("use_parallel", None),
            timeout_minutes=task_config.get("timeout_minutes", 90),
            resume_from_phase=resume_from,
        )

        if result.get("status") == "completed":
            print("\n✅ Build completed successfully")
            return 0
        elif result.get("status") == "paused":
            print(f"\n⏸️  Build paused after {result.get('paused_after')}")
            print(f"   Resume with: cfd resume --dir {project_dir}")
            return 0
        else:
            print(f"\n❌ Build failed: {result.get('error', 'Unknown error')}")
            return 1
    else:
        # Submit to daemon for execution
        store = Store(config.db_path)
        from .jobs import JobManager

        # Add resume_from_phase to task config
        task_config["resume_from_phase"] = resume_from

        job_manager = JobManager(config, store, runner=None)
        job = job_manager.submit_job(
            job_type=JobType.AUTONOMOUS_BUILD,
            params=task_config,
            priority=args.priority,
        )

        print(f"\nJob submitted: {job.id}")
        print(f"  Type: {job.type.value}")
        print(f"  Resume from: {resume_from}")
        print(f"  Status: {job.status.value}")
        print(f"\nMonitor with: cfd logs {job.id} --phases")

        if args.wait:
            print("\nWaiting for job to complete...")
            _wait_for_job(store, job.id, args.timeout)

        return 0


def _wait_for_job(store: Store, job_id: str, timeout: Optional[int] = None):
    """Wait for job to complete"""
    start_time = time.time()

    while True:
        job = store.get_job(job_id)
        if not job:
            print("Job not found")
            return

        if job.status in [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED]:
            print(f"\nJob completed with status: {job.status.value}")
            if job.error:
                print(f"Error: {job.error}")
            return

        # Check timeout
        if timeout and (time.time() - start_time) > timeout:
            print("\nTimeout waiting for job completion")
            return

        time.sleep(2)
        print(".", end="", flush=True)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Context Foundry Daemon - Autonomous build orchestration"
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="Path to config file",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start the daemon")
    start_parser.add_argument(
        "--foreground",
        "-f",
        action="store_true",
        help="Run in foreground mode instead of daemonizing to background",
    )

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop the daemon")
    stop_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout for graceful shutdown (seconds)",
    )

    # Status command
    status_parser = subparsers.add_parser("status", help="Get daemon status")
    status_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed status",
    )

    # Healthcheck command (for supervisors)
    health_parser = subparsers.add_parser(
        "healthcheck", help="Healthcheck and optional auto-restart"
    )
    health_parser.add_argument(
        "--max-stale",
        type=int,
        default=120,
        help="Seconds after which heartbeat is considered unhealthy",
    )
    health_parser.add_argument(
        "--restart",
        action="store_true",
        help="Attempt restart when heartbeat is unhealthy or missing",
    )
    health_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout for graceful shutdown when restarting (seconds)",
    )
    health_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show heartbeat details on warning/unhealthy states",
    )

    # Submit command
    submit_parser = subparsers.add_parser("submit", help="Submit a new job")
    submit_parser.add_argument("--type", required=True, help="Job type")
    submit_parser.add_argument("--params", help="Job parameters (JSON)")
    submit_parser.add_argument(
        "--priority", type=int, default=5, help="Job priority (1-10)"
    )
    submit_parser.add_argument("--max-retries", type=int, help="Maximum retry attempts")
    submit_parser.add_argument(
        "--wait", action="store_true", help="Wait for job to complete"
    )
    submit_parser.add_argument(
        "--timeout", type=int, help="Timeout for --wait (seconds)"
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List jobs")
    list_parser.add_argument("--status", help="Filter by status")
    list_parser.add_argument(
        "--limit", type=int, default=50, help="Maximum jobs to show"
    )
    list_parser.add_argument(
        "--offset", type=int, default=0, help="Offset for pagination"
    )

    # Show command
    show_parser = subparsers.add_parser("show", help="Show job details")
    show_parser.add_argument("job_id", help="Job ID")

    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Show job logs")
    logs_parser.add_argument("job_id", help="Job ID")
    logs_parser.add_argument("--level", help="Filter by log level")
    logs_parser.add_argument(
        "--limit", type=int, default=100, help="Maximum logs to show"
    )
    logs_parser.add_argument(
        "--follow", "-f", action="store_true", help="Follow logs in real-time"
    )
    logs_parser.add_argument(
        "--phases",
        "-p",
        action="store_true",
        help="Show phase breakdown with status and durations",
    )

    # Cancel command
    cancel_parser = subparsers.add_parser("cancel", help="Cancel a job")
    cancel_parser.add_argument("job_id", help="Job ID")

    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up zombie processes")
    cleanup_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Kill all zombies without confirmation",
    )

    # Killall command
    killall_parser = subparsers.add_parser("killall", help="Kill all related processes")
    killall_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Kill all without confirmation",
    )

    # Pipeline-status command
    pipeline_status_parser = subparsers.add_parser(
        "pipeline-status", help="Show pipeline state for a project directory"
    )
    pipeline_status_parser.add_argument(
        "--dir",
        "-d",
        type=str,
        default=".",
        help="Project directory (default: current directory)",
    )

    # Run-phase command (Milestone 2: Selective Phase Execution)
    run_phase_parser = subparsers.add_parser(
        "run-phase", help="Run specific phase(s) with contract validation"
    )
    run_phase_parser.add_argument(
        "phases",
        nargs="*",
        help="Phase(s) to run (e.g., Scout, Architect Builder Test)",
    )
    run_phase_parser.add_argument(
        "--dir",
        "-d",
        type=str,
        default=".",
        help="Project directory (default: current directory)",
    )
    run_phase_parser.add_argument(
        "--with-deps",
        action="store_true",
        help="Include all dependency phases",
    )
    run_phase_parser.add_argument(
        "--skip-contracts",
        action="store_true",
        help="Skip input contract validation",
    )
    run_phase_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Continue even if contracts fail",
    )
    run_phase_parser.add_argument(
        "--priority",
        type=int,
        default=5,
        help="Job priority when submitting to daemon (1-10)",
    )
    run_phase_parser.add_argument(
        "--timeout",
        type=int,
        help="Timeout in minutes (default: 90)",
    )
    run_phase_parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for job to complete",
    )

    # Resume command
    resume_parser = subparsers.add_parser("resume", help="Resume a paused pipeline")
    resume_parser.add_argument(
        "--dir",
        "-d",
        type=str,
        default=".",
        help="Project directory (default: current directory)",
    )
    resume_parser.add_argument(
        "--from",
        dest="from_phase",
        type=str,
        help="Phase to resume from (e.g., Architect, Builder)",
    )
    resume_parser.add_argument(
        "--priority",
        type=int,
        default=5,
        help="Job priority when submitting to daemon (1-10)",
    )
    resume_parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for job to complete",
    )
    resume_parser.add_argument(
        "--timeout",
        type=int,
        help="Timeout for --wait (seconds)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Execute command
    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "healthcheck": cmd_healthcheck,
        "submit": cmd_submit,
        "list": cmd_list,
        "show": cmd_show,
        "logs": cmd_logs,
        "cancel": cmd_cancel,
        "cleanup": cmd_cleanup,
        "killall": cmd_killall,
        "pipeline-status": cmd_pipeline_status,
        "run-phase": cmd_run_phase,
        "resume": cmd_resume,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
