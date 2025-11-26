"""
Human Approval Gates for Context Foundry Pipeline

Explicit authorization for risky phases (e.g., Deploy).
Part of Milestone 5: Human Approval Gates.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import uuid

from .audit import (
    AuditEventType,
    AuditSeverity,
    get_audit_logger,
)
from .pipeline_state import PipelineState, PipelineStateSnapshot


class ApprovalStatus(str, Enum):
    """Status of an approval request"""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


# Default phases that require approval
DEFAULT_APPROVAL_REQUIRED_PHASES = ["Deploy"]

# Approval request storage directory
APPROVAL_DIR = Path.home() / ".context-foundry" / "approvals"


@dataclass
class ApprovalRequest:
    """A request for human approval to proceed with a phase"""

    request_id: str
    phase: str
    pipeline_id: str
    working_directory: str
    status: ApprovalStatus = ApprovalStatus.PENDING

    # Request details
    task_summary: str = ""
    risk_description: str = ""
    changes_summary: str = ""

    # Timing
    requested_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    expires_at: Optional[str] = None
    responded_at: Optional[str] = None

    # Response details
    approved_by: Optional[str] = None
    response_reason: Optional[str] = None

    @classmethod
    def create(
        cls,
        phase: str,
        pipeline_id: str,
        working_directory: str,
        task_summary: str = "",
        risk_description: str = "",
        changes_summary: str = "",
        expiry_hours: int = 24,
    ) -> "ApprovalRequest":
        """
        Create a new approval request.

        Args:
            phase: Phase requiring approval
            pipeline_id: ID of the pipeline
            working_directory: Project directory
            task_summary: Summary of what the phase will do
            risk_description: Description of risks involved
            changes_summary: Summary of changes made so far
            expiry_hours: Hours until request expires

        Returns:
            New ApprovalRequest
        """
        now = datetime.utcnow()
        expires = now + timedelta(hours=expiry_hours)

        return cls(
            request_id=str(uuid.uuid4()),
            phase=phase,
            pipeline_id=pipeline_id,
            working_directory=working_directory,
            status=ApprovalStatus.PENDING,
            task_summary=task_summary,
            risk_description=risk_description,
            changes_summary=changes_summary,
            requested_at=now.isoformat(),
            expires_at=expires.isoformat(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "request_id": self.request_id,
            "phase": self.phase,
            "pipeline_id": self.pipeline_id,
            "working_directory": self.working_directory,
            "status": self.status.value,
            "task_summary": self.task_summary,
            "risk_description": self.risk_description,
            "changes_summary": self.changes_summary,
            "requested_at": self.requested_at,
            "expires_at": self.expires_at,
            "responded_at": self.responded_at,
            "approved_by": self.approved_by,
            "response_reason": self.response_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalRequest":
        """Create from dictionary"""
        return cls(
            request_id=data.get("request_id", str(uuid.uuid4())),
            phase=data.get("phase", ""),
            pipeline_id=data.get("pipeline_id", ""),
            working_directory=data.get("working_directory", ""),
            status=ApprovalStatus(data.get("status", "pending")),
            task_summary=data.get("task_summary", ""),
            risk_description=data.get("risk_description", ""),
            changes_summary=data.get("changes_summary", ""),
            requested_at=data.get("requested_at", ""),
            expires_at=data.get("expires_at"),
            responded_at=data.get("responded_at"),
            approved_by=data.get("approved_by"),
            response_reason=data.get("response_reason"),
        )

    def is_expired(self) -> bool:
        """Check if the request has expired"""
        if not self.expires_at:
            return False
        try:
            expiry = datetime.fromisoformat(self.expires_at)
            return datetime.utcnow() > expiry
        except ValueError:
            return False

    def approve(self, approved_by: str, reason: Optional[str] = None) -> None:
        """Mark the request as approved"""
        self.status = ApprovalStatus.APPROVED
        self.approved_by = approved_by
        self.response_reason = reason
        self.responded_at = datetime.utcnow().isoformat()

    def deny(self, denied_by: str, reason: Optional[str] = None) -> None:
        """Mark the request as denied"""
        self.status = ApprovalStatus.DENIED
        self.approved_by = denied_by  # Reusing field for consistency
        self.response_reason = reason
        self.responded_at = datetime.utcnow().isoformat()

    def get_display_summary(self) -> str:
        """Get a human-readable summary for display"""
        lines = [
            f"Request ID: {self.request_id[:8]}",
            f"Phase: {self.phase}",
            f"Status: {self.status.value.upper()}",
            f"Project: {self.working_directory}",
        ]

        if self.task_summary:
            lines.append(f"Task: {self.task_summary[:100]}")

        if self.risk_description:
            lines.append(f"Risk: {self.risk_description}")

        if self.requested_at:
            lines.append(f"Requested: {self.requested_at}")

        if self.status == ApprovalStatus.PENDING and self.expires_at:
            lines.append(f"Expires: {self.expires_at}")

        if self.responded_at:
            lines.append(f"Responded: {self.responded_at}")
            if self.approved_by:
                lines.append(f"By: {self.approved_by}")
            if self.response_reason:
                lines.append(f"Reason: {self.response_reason}")

        return "\n".join(lines)


class ApprovalGateConfig:
    """Configuration for approval gates"""

    def __init__(
        self,
        require_approval_phases: Optional[List[str]] = None,
        auto_approve_phases: Optional[List[str]] = None,
        expiry_hours: int = 24,
    ):
        """
        Initialize approval gate configuration.

        Args:
            require_approval_phases: Phases requiring approval (default: ["Deploy"])
            auto_approve_phases: Phases to auto-approve (bypass gates)
            expiry_hours: Hours until approval requests expire
        """
        self.require_approval_phases = (
            require_approval_phases or DEFAULT_APPROVAL_REQUIRED_PHASES
        )
        self.auto_approve_phases = auto_approve_phases or []
        self.expiry_hours = expiry_hours

    def requires_approval(self, phase: str) -> bool:
        """Check if a phase requires approval"""
        if phase in self.auto_approve_phases:
            return False
        return phase in self.require_approval_phases

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "require_approval_phases": self.require_approval_phases,
            "auto_approve_phases": self.auto_approve_phases,
            "expiry_hours": self.expiry_hours,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApprovalGateConfig":
        """Create from dictionary"""
        return cls(
            require_approval_phases=data.get("require_approval_phases"),
            auto_approve_phases=data.get("auto_approve_phases"),
            expiry_hours=data.get("expiry_hours", 24),
        )


class ApprovalManager:
    """
    Manages approval requests and responses.

    Stores requests in ~/.context-foundry/approvals/ as JSON files.
    """

    def __init__(self, config: Optional[ApprovalGateConfig] = None):
        """
        Initialize approval manager.

        Args:
            config: Approval gate configuration
        """
        self.config = config or ApprovalGateConfig()
        self._ensure_approval_dir()

    def _ensure_approval_dir(self) -> None:
        """Ensure approval directory exists"""
        APPROVAL_DIR.mkdir(parents=True, exist_ok=True)

    def _get_request_file(self, request_id: str) -> Path:
        """Get path to request file"""
        return APPROVAL_DIR / f"{request_id}.json"

    def _get_pending_file(self, pipeline_id: str, phase: str) -> Path:
        """Get path to pending approval marker file"""
        return APPROVAL_DIR / f"pending_{pipeline_id[:8]}_{phase}.json"

    def create_request(
        self,
        phase: str,
        pipeline_id: str,
        working_directory: str,
        task_summary: str = "",
        risk_description: str = "",
        changes_summary: str = "",
    ) -> ApprovalRequest:
        """
        Create and store a new approval request.

        Args:
            phase: Phase requiring approval
            pipeline_id: Pipeline ID
            working_directory: Project directory
            task_summary: Summary of the task
            risk_description: Description of risks
            changes_summary: Summary of changes

        Returns:
            New ApprovalRequest
        """
        request = ApprovalRequest.create(
            phase=phase,
            pipeline_id=pipeline_id,
            working_directory=working_directory,
            task_summary=task_summary,
            risk_description=risk_description,
            changes_summary=changes_summary,
            expiry_hours=self.config.expiry_hours,
        )

        # Save request
        self._save_request(request)

        # Log to audit
        get_audit_logger().log(
            event_type=AuditEventType.APPROVAL_REQUESTED,
            message=f"Approval requested for {phase}",
            severity=AuditSeverity.WARNING,
            phase=phase,
            job_id=pipeline_id,
            working_directory=working_directory,
            details={
                "request_id": request.request_id,
                "task_summary": task_summary,
                "risk_description": risk_description,
            },
        )

        return request

    def _save_request(self, request: ApprovalRequest) -> None:
        """Save request to file"""
        request_file = self._get_request_file(request.request_id)
        request_file.write_text(json.dumps(request.to_dict(), indent=2))

        # Also save as pending marker for easy lookup
        if request.status == ApprovalStatus.PENDING:
            pending_file = self._get_pending_file(request.pipeline_id, request.phase)
            pending_file.write_text(json.dumps({"request_id": request.request_id}))

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """
        Get an approval request by ID.

        Args:
            request_id: Request ID

        Returns:
            ApprovalRequest or None
        """
        request_file = self._get_request_file(request_id)
        if not request_file.exists():
            return None

        try:
            data = json.loads(request_file.read_text())
            request = ApprovalRequest.from_dict(data)

            # Check for expiration
            if request.status == ApprovalStatus.PENDING and request.is_expired():
                request.status = ApprovalStatus.EXPIRED
                self._save_request(request)

            return request
        except (json.JSONDecodeError, KeyError):
            return None

    def get_pending_request(
        self, pipeline_id: str, phase: str
    ) -> Optional[ApprovalRequest]:
        """
        Get pending approval request for a pipeline phase.

        Args:
            pipeline_id: Pipeline ID
            phase: Phase name

        Returns:
            Pending ApprovalRequest or None
        """
        pending_file = self._get_pending_file(pipeline_id, phase)
        if not pending_file.exists():
            return None

        try:
            data = json.loads(pending_file.read_text())
            request_id = data.get("request_id")
            if request_id:
                return self.get_request(request_id)
        except json.JSONDecodeError:
            pass

        return None

    def approve_request(
        self,
        request_id: str,
        approved_by: str,
        reason: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        """
        Approve a request.

        Args:
            request_id: Request ID to approve
            approved_by: Who is approving
            reason: Optional reason

        Returns:
            Updated ApprovalRequest or None
        """
        request = self.get_request(request_id)
        if not request:
            return None

        if request.status != ApprovalStatus.PENDING:
            return request  # Already processed

        request.approve(approved_by, reason)
        self._save_request(request)

        # Remove pending marker
        pending_file = self._get_pending_file(request.pipeline_id, request.phase)
        if pending_file.exists():
            pending_file.unlink()

        # Log to audit
        get_audit_logger().log(
            event_type=AuditEventType.APPROVAL_GRANTED,
            message=f"Approval granted for {request.phase}",
            severity=AuditSeverity.INFO,
            phase=request.phase,
            job_id=request.pipeline_id,
            working_directory=request.working_directory,
            details={
                "request_id": request_id,
                "approved_by": approved_by,
                "reason": reason,
            },
        )

        return request

    def deny_request(
        self,
        request_id: str,
        denied_by: str,
        reason: Optional[str] = None,
    ) -> Optional[ApprovalRequest]:
        """
        Deny a request.

        Args:
            request_id: Request ID to deny
            denied_by: Who is denying
            reason: Optional reason

        Returns:
            Updated ApprovalRequest or None
        """
        request = self.get_request(request_id)
        if not request:
            return None

        if request.status != ApprovalStatus.PENDING:
            return request  # Already processed

        request.deny(denied_by, reason)
        self._save_request(request)

        # Remove pending marker
        pending_file = self._get_pending_file(request.pipeline_id, request.phase)
        if pending_file.exists():
            pending_file.unlink()

        # Log to audit
        get_audit_logger().log(
            event_type=AuditEventType.APPROVAL_DENIED,
            message=f"Approval denied for {request.phase}",
            severity=AuditSeverity.WARNING,
            phase=request.phase,
            job_id=request.pipeline_id,
            working_directory=request.working_directory,
            details={
                "request_id": request_id,
                "denied_by": denied_by,
                "reason": reason,
            },
        )

        return request

    def list_pending_requests(self) -> List[ApprovalRequest]:
        """
        List all pending approval requests.

        Returns:
            List of pending ApprovalRequests
        """
        pending = []
        for file in APPROVAL_DIR.glob("pending_*.json"):
            try:
                data = json.loads(file.read_text())
                request_id = data.get("request_id")
                if request_id:
                    request = self.get_request(request_id)
                    if request and request.status == ApprovalStatus.PENDING:
                        pending.append(request)
            except json.JSONDecodeError:
                continue

        # Sort by requested_at
        pending.sort(key=lambda r: r.requested_at or "", reverse=True)
        return pending

    def list_all_requests(self, limit: int = 50) -> List[ApprovalRequest]:
        """
        List all approval requests.

        Args:
            limit: Maximum number to return

        Returns:
            List of ApprovalRequests (most recent first)
        """
        requests = []
        for file in APPROVAL_DIR.glob("*.json"):
            if file.name.startswith("pending_"):
                continue  # Skip marker files
            try:
                data = json.loads(file.read_text())
                request = ApprovalRequest.from_dict(data)
                requests.append(request)
            except (json.JSONDecodeError, KeyError):
                continue

        # Sort by requested_at (most recent first)
        requests.sort(key=lambda r: r.requested_at or "", reverse=True)
        return requests[:limit]

    def cleanup_expired(self) -> int:
        """
        Clean up expired requests.

        Returns:
            Number of requests expired
        """
        count = 0
        for file in APPROVAL_DIR.glob("pending_*.json"):
            try:
                data = json.loads(file.read_text())
                request_id = data.get("request_id")
                if request_id:
                    request = self.get_request(request_id)
                    if request and request.is_expired():
                        request.status = ApprovalStatus.EXPIRED
                        self._save_request(request)
                        file.unlink()
                        count += 1
            except json.JSONDecodeError:
                continue

        return count


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def check_approval_required(
    phase: str,
    pipeline_state: Optional[PipelineStateSnapshot] = None,
    config: Optional[ApprovalGateConfig] = None,
) -> bool:
    """
    Check if approval is required for a phase.

    Args:
        phase: Phase name
        pipeline_state: Optional pipeline state (may contain approval config)
        config: Optional approval config override

    Returns:
        True if approval required
    """
    if config is None:
        config = ApprovalGateConfig()

    return config.requires_approval(phase)


def request_approval_for_phase(
    phase: str,
    pipeline_state: PipelineStateSnapshot,
    task_summary: str = "",
    risk_description: str = "",
    changes_summary: str = "",
) -> ApprovalRequest:
    """
    Request approval for a phase.

    Updates pipeline state to WAITING_APPROVAL and creates an approval request.

    Args:
        phase: Phase requiring approval
        pipeline_state: Current pipeline state
        task_summary: Summary of what the phase will do
        risk_description: Description of risks
        changes_summary: Summary of changes made

    Returns:
        ApprovalRequest
    """
    manager = ApprovalManager()

    # Create request
    request = manager.create_request(
        phase=phase,
        pipeline_id=pipeline_state.pipeline_id,
        working_directory=pipeline_state.task_config.get("working_directory", ""),
        task_summary=task_summary,
        risk_description=risk_description,
        changes_summary=changes_summary,
    )

    # Update pipeline state
    pipeline_state.state = PipelineState.WAITING_APPROVAL
    pipeline_state.paused_at = datetime.utcnow().isoformat()

    return request


def check_approval_status(
    pipeline_id: str,
    phase: str,
) -> Optional[ApprovalRequest]:
    """
    Check approval status for a pipeline phase.

    Args:
        pipeline_id: Pipeline ID
        phase: Phase name

    Returns:
        ApprovalRequest if exists, None otherwise
    """
    manager = ApprovalManager()
    return manager.get_pending_request(pipeline_id, phase)


def approve_phase(
    request_id: str,
    approved_by: str,
    reason: Optional[str] = None,
) -> Optional[ApprovalRequest]:
    """
    Approve a phase request.

    Args:
        request_id: Request ID to approve
        approved_by: Who is approving
        reason: Optional reason

    Returns:
        Updated ApprovalRequest
    """
    manager = ApprovalManager()
    return manager.approve_request(request_id, approved_by, reason)


def deny_phase(
    request_id: str,
    denied_by: str,
    reason: Optional[str] = None,
) -> Optional[ApprovalRequest]:
    """
    Deny a phase request.

    Args:
        request_id: Request ID to deny
        denied_by: Who is denying
        reason: Optional reason

    Returns:
        Updated ApprovalRequest
    """
    manager = ApprovalManager()
    return manager.deny_request(request_id, denied_by, reason)


def list_pending_approvals() -> List[ApprovalRequest]:
    """
    List all pending approval requests.

    Returns:
        List of pending ApprovalRequests
    """
    manager = ApprovalManager()
    return manager.list_pending_requests()


def get_default_risk_description(phase: str) -> str:
    """
    Get default risk description for a phase.

    Args:
        phase: Phase name

    Returns:
        Risk description string
    """
    risk_descriptions = {
        "Deploy": "This will push changes to a remote repository and potentially trigger deployment pipelines.",
        "Test": "This will execute test suites which may have side effects.",
        "Builder": "This will modify source files in the project.",
    }
    return risk_descriptions.get(phase, f"Executing {phase} phase.")
