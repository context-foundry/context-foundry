"""
Tests for Milestone 5: Human Approval Gates

Tests the approval gate system including:
- ApprovalRequest creation and lifecycle
- ApprovalManager operations
- ApprovalGateConfig
- Integration with pipeline state
"""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from tools.mcp_utils.approval_gates import (
    ApprovalGateConfig,
    ApprovalManager,
    ApprovalRequest,
    ApprovalStatus,
    APPROVAL_DIR,
    check_approval_required,
    approve_phase,
    deny_phase,
    list_pending_approvals,
    get_default_risk_description,
)
from tools.mcp_utils.pipeline_state import PipelineState, PipelineStateSnapshot


@pytest.fixture
def temp_approval_dir():
    """Create a temporary approval directory for testing"""
    original_dir = APPROVAL_DIR
    temp_dir = Path(tempfile.mkdtemp()) / "approvals"
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Patch the APPROVAL_DIR
    import tools.mcp_utils.approval_gates as ag

    ag.APPROVAL_DIR = temp_dir

    yield temp_dir

    # Restore and cleanup
    ag.APPROVAL_DIR = original_dir
    shutil.rmtree(temp_dir.parent)


class TestApprovalRequest:
    """Tests for ApprovalRequest dataclass"""

    def test_create_request(self):
        """Test creating an approval request"""
        request = ApprovalRequest.create(
            phase="Deploy",
            pipeline_id="test-pipeline-123",
            working_directory="/tmp/test-project",
            task_summary="Deploy to GitHub",
            risk_description="Will push to remote",
        )

        assert request.phase == "Deploy"
        assert request.pipeline_id == "test-pipeline-123"
        assert request.status == ApprovalStatus.PENDING
        assert request.task_summary == "Deploy to GitHub"
        assert request.risk_description == "Will push to remote"
        assert request.request_id is not None
        assert request.requested_at is not None
        assert request.expires_at is not None

    def test_request_to_dict(self):
        """Test serialization to dictionary"""
        request = ApprovalRequest.create(
            phase="Deploy",
            pipeline_id="test-123",
            working_directory="/tmp/test",
        )

        data = request.to_dict()

        assert data["phase"] == "Deploy"
        assert data["pipeline_id"] == "test-123"
        assert data["status"] == "pending"
        assert "request_id" in data

    def test_request_from_dict(self):
        """Test deserialization from dictionary"""
        data = {
            "request_id": "req-123",
            "phase": "Deploy",
            "pipeline_id": "pipe-456",
            "working_directory": "/tmp/test",
            "status": "pending",
            "requested_at": "2024-01-01T00:00:00",
        }

        request = ApprovalRequest.from_dict(data)

        assert request.request_id == "req-123"
        assert request.phase == "Deploy"
        assert request.status == ApprovalStatus.PENDING

    def test_approve_request(self):
        """Test approving a request"""
        request = ApprovalRequest.create(
            phase="Deploy",
            pipeline_id="test-123",
            working_directory="/tmp/test",
        )

        request.approve("test_user", "Looks good")

        assert request.status == ApprovalStatus.APPROVED
        assert request.approved_by == "test_user"
        assert request.response_reason == "Looks good"
        assert request.responded_at is not None

    def test_deny_request(self):
        """Test denying a request"""
        request = ApprovalRequest.create(
            phase="Deploy",
            pipeline_id="test-123",
            working_directory="/tmp/test",
        )

        request.deny("test_user", "Not ready yet")

        assert request.status == ApprovalStatus.DENIED
        assert request.approved_by == "test_user"
        assert request.response_reason == "Not ready yet"

    def test_is_expired(self):
        """Test expiration check"""
        request = ApprovalRequest.create(
            phase="Deploy",
            pipeline_id="test-123",
            working_directory="/tmp/test",
            expiry_hours=0,  # Immediate expiry
        )

        # Request should be expired immediately
        assert request.is_expired() is True

    def test_display_summary(self):
        """Test display summary generation"""
        request = ApprovalRequest.create(
            phase="Deploy",
            pipeline_id="test-123",
            working_directory="/tmp/test",
            task_summary="Deploy app",
        )

        summary = request.get_display_summary()

        assert "Deploy" in summary
        assert "test-123"[:8] in summary or request.request_id[:8] in summary
        assert "PENDING" in summary


class TestApprovalGateConfig:
    """Tests for ApprovalGateConfig"""

    def test_default_config(self):
        """Test default configuration"""
        config = ApprovalGateConfig()

        assert "Deploy" in config.require_approval_phases
        assert config.requires_approval("Deploy") is True
        assert config.requires_approval("Scout") is False

    def test_custom_config(self):
        """Test custom configuration"""
        config = ApprovalGateConfig(
            require_approval_phases=["Deploy", "Builder"],
            auto_approve_phases=["Deploy"],
        )

        # Deploy is in auto_approve, so it should NOT require approval
        assert config.requires_approval("Deploy") is False
        # Builder requires approval
        assert config.requires_approval("Builder") is True

    def test_config_serialization(self):
        """Test config to/from dict"""
        config = ApprovalGateConfig(
            require_approval_phases=["Deploy"],
            expiry_hours=12,
        )

        data = config.to_dict()
        restored = ApprovalGateConfig.from_dict(data)

        assert restored.require_approval_phases == ["Deploy"]
        assert restored.expiry_hours == 12


class TestApprovalManager:
    """Tests for ApprovalManager"""

    def test_create_request(self, temp_approval_dir):
        """Test creating a request through manager"""
        manager = ApprovalManager()

        request = manager.create_request(
            phase="Deploy",
            pipeline_id="test-pipeline",
            working_directory="/tmp/test",
            task_summary="Test deployment",
        )

        assert request.status == ApprovalStatus.PENDING
        assert request.request_id is not None

        # Verify file was created
        request_file = temp_approval_dir / f"{request.request_id}.json"
        assert request_file.exists()

    def test_get_request(self, temp_approval_dir):
        """Test retrieving a request"""
        manager = ApprovalManager()

        # Create request
        created = manager.create_request(
            phase="Deploy",
            pipeline_id="test-pipeline",
            working_directory="/tmp/test",
        )

        # Retrieve it
        retrieved = manager.get_request(created.request_id)

        assert retrieved is not None
        assert retrieved.request_id == created.request_id
        assert retrieved.phase == "Deploy"

    def test_approve_request(self, temp_approval_dir):
        """Test approving a request through manager"""
        manager = ApprovalManager()

        # Create request
        request = manager.create_request(
            phase="Deploy",
            pipeline_id="test-pipeline",
            working_directory="/tmp/test",
        )

        # Approve it
        result = manager.approve_request(
            request.request_id,
            approved_by="test_user",
            reason="LGTM",
        )

        assert result.status == ApprovalStatus.APPROVED
        assert result.approved_by == "test_user"

        # Verify pending marker was removed
        pending_file = temp_approval_dir / "pending_test-pip_Deploy.json"
        assert not pending_file.exists()

    def test_deny_request(self, temp_approval_dir):
        """Test denying a request through manager"""
        manager = ApprovalManager()

        # Create request
        request = manager.create_request(
            phase="Deploy",
            pipeline_id="test-pipeline",
            working_directory="/tmp/test",
        )

        # Deny it
        result = manager.deny_request(
            request.request_id,
            denied_by="test_user",
            reason="Not ready",
        )

        assert result.status == ApprovalStatus.DENIED

    def test_list_pending_requests(self, temp_approval_dir):
        """Test listing pending requests"""
        manager = ApprovalManager()

        # Create multiple requests for DIFFERENT pipelines
        # (pending markers are keyed by pipeline_id + phase, so same phase is fine)
        manager.create_request(
            phase="Deploy",
            pipeline_id="pipeline-1",
            working_directory="/tmp/test1",
        )
        manager.create_request(
            phase="Builder",  # Different phase
            pipeline_id="pipeline-2",
            working_directory="/tmp/test2",
        )

        pending = manager.list_pending_requests()

        assert len(pending) == 2

    def test_list_all_requests(self, temp_approval_dir):
        """Test listing all requests"""
        manager = ApprovalManager()

        # Create and approve one request
        req1 = manager.create_request(
            phase="Deploy",
            pipeline_id="pipeline-1",
            working_directory="/tmp/test1",
        )
        manager.approve_request(req1.request_id, "user")

        # Create another pending request
        manager.create_request(
            phase="Deploy",
            pipeline_id="pipeline-2",
            working_directory="/tmp/test2",
        )

        all_requests = manager.list_all_requests()

        assert len(all_requests) == 2

    def test_get_pending_request_for_pipeline(self, temp_approval_dir):
        """Test getting pending request for specific pipeline/phase"""
        manager = ApprovalManager()

        # Create request
        created = manager.create_request(
            phase="Deploy",
            pipeline_id="specific-pipeline",
            working_directory="/tmp/test",
        )

        # Find it
        found = manager.get_pending_request("specific-pipeline", "Deploy")

        assert found is not None
        assert found.request_id == created.request_id


class TestHelperFunctions:
    """Tests for module-level helper functions"""

    def test_check_approval_required_default(self):
        """Test default approval requirements"""
        assert check_approval_required("Deploy") is True
        assert check_approval_required("Scout") is False
        assert check_approval_required("Builder") is False

    def test_check_approval_required_custom_config(self):
        """Test with custom config"""
        config = ApprovalGateConfig(require_approval_phases=["Builder", "Deploy"])

        assert check_approval_required("Builder", config=config) is True
        assert check_approval_required("Deploy", config=config) is True
        assert check_approval_required("Scout", config=config) is False

    def test_get_default_risk_description(self):
        """Test default risk descriptions"""
        deploy_risk = get_default_risk_description("Deploy")
        assert "GitHub" in deploy_risk or "deployment" in deploy_risk

        unknown_risk = get_default_risk_description("Unknown")
        assert "Unknown" in unknown_risk

    def test_approve_phase_helper(self, temp_approval_dir):
        """Test approve_phase helper function"""
        manager = ApprovalManager()
        request = manager.create_request(
            phase="Deploy",
            pipeline_id="test-pipeline",
            working_directory="/tmp/test",
        )

        result = approve_phase(request.request_id, "test_user", "Approved")

        assert result.status == ApprovalStatus.APPROVED

    def test_deny_phase_helper(self, temp_approval_dir):
        """Test deny_phase helper function"""
        manager = ApprovalManager()
        request = manager.create_request(
            phase="Deploy",
            pipeline_id="test-pipeline",
            working_directory="/tmp/test",
        )

        result = deny_phase(request.request_id, "test_user", "Denied")

        assert result.status == ApprovalStatus.DENIED

    def test_list_pending_approvals_helper(self, temp_approval_dir):
        """Test list_pending_approvals helper function"""
        manager = ApprovalManager()
        manager.create_request(
            phase="Deploy",
            pipeline_id="test-pipeline",
            working_directory="/tmp/test",
        )

        pending = list_pending_approvals()

        assert len(pending) == 1


class TestPipelineIntegration:
    """Tests for pipeline state integration"""

    def test_waiting_approval_state(self):
        """Test that WAITING_APPROVAL is a valid pipeline state"""
        assert PipelineState.WAITING_APPROVAL in PipelineState.resumable_states()

    def test_pipeline_state_with_approval(self, temp_approval_dir):
        """Test pipeline state transitions with approval"""
        # Create pipeline state
        state = PipelineStateSnapshot.create(
            task_config={
                "task": "Test task",
                "working_directory": "/tmp/test",
            },
            execution_mode="interactive",
        )

        # Simulate approval request
        state.state = PipelineState.WAITING_APPROVAL
        state.paused_at = datetime.utcnow().isoformat()

        assert state.state == PipelineState.WAITING_APPROVAL
        assert state.state in PipelineState.resumable_states()
