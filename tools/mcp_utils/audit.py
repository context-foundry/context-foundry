"""
Audit Logging for Context Foundry Pipeline

Centralized logging system for safety events.
Part of Milestone 3: Safety Mechanisms.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import sys
import threading

# fcntl is Unix-only; use msvcrt on Windows for file locking
if sys.platform == 'win32':
    import msvcrt
    HAVE_FCNTL = False
else:
    import fcntl
    HAVE_FCNTL = True

# Default audit log location
DEFAULT_AUDIT_DIR = Path.home() / ".context-foundry" / "audit"
DEFAULT_AUDIT_FILE = DEFAULT_AUDIT_DIR / "safety-audit.jsonl"


class AuditEventType(str, Enum):
    """Types of auditable events"""

    # Pre-flight events
    PREFLIGHT_STARTED = "preflight_started"
    PREFLIGHT_PASSED = "preflight_passed"
    PREFLIGHT_FAILED = "preflight_failed"
    PREFLIGHT_WARNING = "preflight_warning"

    # Scope events
    SCOPE_VIOLATION = "scope_violation"
    SCOPE_CHECK_PASSED = "scope_check_passed"

    # Phase events
    PHASE_STARTED = "phase_started"
    PHASE_COMPLETED = "phase_completed"
    PHASE_FAILED = "phase_failed"
    PHASE_SKIPPED = "phase_skipped"
    PHASE_PAUSED = "phase_paused"
    PHASE_RESUMED = "phase_resumed"

    # Pipeline events
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_FAILED = "pipeline_failed"
    PIPELINE_CANCELLED = "pipeline_cancelled"
    EMERGENCY_STOP = "emergency_stop"

    # Approval events
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"

    # Error events
    ERROR = "error"
    WARNING = "warning"


class AuditSeverity(str, Enum):
    """Severity levels for audit events"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """A single audit event"""

    event_type: AuditEventType
    severity: AuditSeverity
    message: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    phase: Optional[str] = None
    job_id: Optional[str] = None
    working_directory: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    source: str = "context-foundry"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "source": self.source,
        }
        if self.phase:
            result["phase"] = self.phase
        if self.job_id:
            result["job_id"] = self.job_id
        if self.working_directory:
            result["working_directory"] = self.working_directory
        if self.details:
            result["details"] = self.details
        return result

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())


class AuditLogger:
    """
    Centralized audit logging for safety events.

    Writes to ~/.context-foundry/audit/safety-audit.jsonl in append-only mode.
    Thread-safe with file locking for concurrent access.
    """

    _instance: Optional["AuditLogger"] = None
    _lock = threading.Lock()

    def __new__(cls, audit_file: Optional[Path] = None):
        """Singleton pattern for global audit logger"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, audit_file: Optional[Path] = None):
        if self._initialized:
            return
        self._initialized = True
        self.audit_file = audit_file or DEFAULT_AUDIT_FILE
        self._ensure_audit_dir()

    def _ensure_audit_dir(self):
        """Ensure audit directory exists"""
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)

    def _write_event(self, event: AuditEvent):
        """Write event to audit log with file locking"""
        try:
            with open(self.audit_file, "a") as f:
                # Get exclusive lock for writing (platform-specific)
                if HAVE_FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                else:
                    # Windows: use msvcrt.locking
                    msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    f.write(event.to_json() + "\n")
                    f.flush()
                finally:
                    if HAVE_FCNTL:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                    else:
                        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError as e:
            # Fallback: print to stderr if file write fails
            print(f"AUDIT LOG WRITE FAILED: {e}", file=sys.stderr)
            print(f"EVENT: {event.to_json()}", file=sys.stderr)

    def log(
        self,
        event_type: AuditEventType,
        message: str,
        severity: AuditSeverity = AuditSeverity.INFO,
        phase: Optional[str] = None,
        job_id: Optional[str] = None,
        working_directory: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Log an audit event.

        Args:
            event_type: Type of event
            message: Human-readable description
            severity: Event severity level
            phase: Pipeline phase (if applicable)
            job_id: Job identifier (if applicable)
            working_directory: Working directory path
            details: Additional event details
        """
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            message=message,
            phase=phase,
            job_id=job_id,
            working_directory=working_directory,
            details=details,
        )
        self._write_event(event)

    # Convenience methods for common events

    def log_preflight_started(
        self, phase: str, working_directory: str, job_id: Optional[str] = None
    ):
        """Log pre-flight check started"""
        self.log(
            event_type=AuditEventType.PREFLIGHT_STARTED,
            message=f"Pre-flight checks started for {phase}",
            severity=AuditSeverity.INFO,
            phase=phase,
            job_id=job_id,
            working_directory=working_directory,
        )

    def log_preflight_passed(
        self, phase: str, working_directory: str, job_id: Optional[str] = None
    ):
        """Log pre-flight check passed"""
        self.log(
            event_type=AuditEventType.PREFLIGHT_PASSED,
            message=f"Pre-flight checks passed for {phase}",
            severity=AuditSeverity.INFO,
            phase=phase,
            job_id=job_id,
            working_directory=working_directory,
        )

    def log_preflight_failed(
        self,
        phase: str,
        working_directory: str,
        failures: List[Dict],
        job_id: Optional[str] = None,
    ):
        """Log pre-flight check failed"""
        self.log(
            event_type=AuditEventType.PREFLIGHT_FAILED,
            message=f"Pre-flight checks failed for {phase}",
            severity=AuditSeverity.ERROR,
            phase=phase,
            job_id=job_id,
            working_directory=working_directory,
            details={"failures": failures},
        )

    def log_scope_violation(
        self,
        phase: str,
        attempted_path: str,
        violation_type: str,
        working_directory: str,
        job_id: Optional[str] = None,
    ):
        """Log a scope violation attempt"""
        self.log(
            event_type=AuditEventType.SCOPE_VIOLATION,
            message=f"Scope violation in {phase}: {violation_type}",
            severity=AuditSeverity.CRITICAL,
            phase=phase,
            job_id=job_id,
            working_directory=working_directory,
            details={
                "attempted_path": attempted_path,
                "violation_type": violation_type,
            },
        )

    def log_phase_started(
        self, phase: str, working_directory: str, job_id: Optional[str] = None
    ):
        """Log phase started"""
        self.log(
            event_type=AuditEventType.PHASE_STARTED,
            message=f"Phase {phase} started",
            severity=AuditSeverity.INFO,
            phase=phase,
            job_id=job_id,
            working_directory=working_directory,
        )

    def log_phase_completed(
        self, phase: str, working_directory: str, job_id: Optional[str] = None
    ):
        """Log phase completed"""
        self.log(
            event_type=AuditEventType.PHASE_COMPLETED,
            message=f"Phase {phase} completed",
            severity=AuditSeverity.INFO,
            phase=phase,
            job_id=job_id,
            working_directory=working_directory,
        )

    def log_phase_failed(
        self,
        phase: str,
        working_directory: str,
        error: str,
        job_id: Optional[str] = None,
    ):
        """Log phase failed"""
        self.log(
            event_type=AuditEventType.PHASE_FAILED,
            message=f"Phase {phase} failed: {error}",
            severity=AuditSeverity.ERROR,
            phase=phase,
            job_id=job_id,
            working_directory=working_directory,
            details={"error": error},
        )

    def log_emergency_stop(
        self,
        reason: str,
        working_directory: str,
        phase: Optional[str] = None,
        job_id: Optional[str] = None,
    ):
        """Log emergency stop triggered"""
        self.log(
            event_type=AuditEventType.EMERGENCY_STOP,
            message=f"Emergency stop: {reason}",
            severity=AuditSeverity.CRITICAL,
            phase=phase,
            job_id=job_id,
            working_directory=working_directory,
            details={"reason": reason},
        )

    def read_recent_events(
        self,
        limit: int = 50,
        event_types: Optional[List[AuditEventType]] = None,
        severity_min: Optional[AuditSeverity] = None,
    ) -> List[Dict[str, Any]]:
        """
        Read recent audit events.

        Args:
            limit: Maximum number of events to return
            event_types: Filter by event types
            severity_min: Minimum severity level

        Returns:
            List of event dictionaries (most recent first)
        """
        if not self.audit_file.exists():
            return []

        severity_order = {
            AuditSeverity.INFO: 0,
            AuditSeverity.WARNING: 1,
            AuditSeverity.ERROR: 2,
            AuditSeverity.CRITICAL: 3,
        }

        events = []
        try:
            with open(self.audit_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                        # Filter by event type
                        if event_types:
                            if event.get("event_type") not in [
                                et.value for et in event_types
                            ]:
                                continue
                        # Filter by severity
                        if severity_min:
                            event_severity = AuditSeverity(
                                event.get("severity", "info")
                            )
                            if severity_order.get(
                                event_severity, 0
                            ) < severity_order.get(severity_min, 0):
                                continue
                        events.append(event)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []

        # Return most recent first
        return events[-limit:][::-1]


# Global logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


def reset_audit_logger():
    """Reset the global audit logger (for testing)"""
    global _audit_logger
    AuditLogger._instance = None
    _audit_logger = None


# Convenience functions for common logging operations
def audit_preflight_started(
    phase: str, working_directory: str, job_id: Optional[str] = None
):
    get_audit_logger().log_preflight_started(phase, working_directory, job_id)


def audit_preflight_passed(
    phase: str, working_directory: str, job_id: Optional[str] = None
):
    get_audit_logger().log_preflight_passed(phase, working_directory, job_id)


def audit_preflight_failed(
    phase: str,
    working_directory: str,
    failures: List[Dict],
    job_id: Optional[str] = None,
):
    get_audit_logger().log_preflight_failed(phase, working_directory, failures, job_id)


def audit_scope_violation(
    phase: str,
    attempted_path: str,
    violation_type: str,
    working_directory: str,
    job_id: Optional[str] = None,
):
    get_audit_logger().log_scope_violation(
        phase, attempted_path, violation_type, working_directory, job_id
    )


def audit_phase_started(
    phase: str, working_directory: str, job_id: Optional[str] = None
):
    get_audit_logger().log_phase_started(phase, working_directory, job_id)


def audit_phase_completed(
    phase: str, working_directory: str, job_id: Optional[str] = None
):
    get_audit_logger().log_phase_completed(phase, working_directory, job_id)


def audit_phase_failed(
    phase: str, working_directory: str, error: str, job_id: Optional[str] = None
):
    get_audit_logger().log_phase_failed(phase, working_directory, error, job_id)


def audit_emergency_stop(
    reason: str,
    working_directory: str,
    phase: Optional[str] = None,
    job_id: Optional[str] = None,
):
    get_audit_logger().log_emergency_stop(reason, working_directory, phase, job_id)


def audit_pipeline_started(
    working_directory: str,
    task: str,
    job_id: Optional[str] = None,
):
    """Log pipeline started"""
    get_audit_logger().log(
        event_type=AuditEventType.PIPELINE_STARTED,
        message=f"Pipeline started: {task[:100]}",
        severity=AuditSeverity.INFO,
        job_id=job_id,
        working_directory=working_directory,
        details={"task": task},
    )


def audit_pipeline_completed(
    working_directory: str,
    phases_completed: List[str],
    job_id: Optional[str] = None,
):
    """Log pipeline completed"""
    get_audit_logger().log(
        event_type=AuditEventType.PIPELINE_COMPLETED,
        message=f"Pipeline completed: {len(phases_completed)} phases",
        severity=AuditSeverity.INFO,
        job_id=job_id,
        working_directory=working_directory,
        details={"phases_completed": phases_completed},
    )


def audit_pipeline_failed(
    working_directory: str,
    error: str,
    phase: Optional[str] = None,
    job_id: Optional[str] = None,
):
    """Log pipeline failed"""
    get_audit_logger().log(
        event_type=AuditEventType.PIPELINE_FAILED,
        message=f"Pipeline failed: {error}",
        severity=AuditSeverity.ERROR,
        phase=phase,
        job_id=job_id,
        working_directory=working_directory,
        details={"error": error},
    )
