import { useState } from 'react';
import { useApprovalsStore, useSelectedApproval } from '../../stores/approvals';

export function ApprovalModal() {
  const { pendingApprovals, closeModal, approve, deny, isLoading, selectApproval } =
    useApprovalsStore();
  const selectedApproval = useSelectedApproval();
  const [denyReason, setDenyReason] = useState('');
  const [showDenyInput, setShowDenyInput] = useState(false);

  const handleApprove = async () => {
    if (selectedApproval) {
      await approve(selectedApproval.id);
    }
  };

  const handleDeny = async () => {
    if (selectedApproval) {
      await deny(selectedApproval.id, denyReason);
      setDenyReason('');
      setShowDenyInput(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={closeModal}>
      <div className="modal approval-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Pending Approvals ({pendingApprovals.length})</h2>
          <button className="modal-close" onClick={closeModal}>
            &times;
          </button>
        </div>

        <div className="approval-content">
          {pendingApprovals.length === 0 ? (
            <div className="approval-empty">No pending approvals</div>
          ) : (
            <>
              <div className="approval-list">
                {pendingApprovals.map((approval) => (
                  <div
                    key={approval.id}
                    className={`approval-item ${selectedApproval?.id === approval.id ? 'selected' : ''}`}
                    onClick={() => selectApproval(approval.id)}
                  >
                    <div className="approval-type">{approval.approval_type}</div>
                    <div className="approval-phase">Phase: {approval.phase}</div>
                    <div className="approval-time">
                      {new Date(approval.created_at).toLocaleTimeString()}
                    </div>
                  </div>
                ))}
              </div>

              {selectedApproval && (
                <div className="approval-detail">
                  <h3>{selectedApproval.approval_type.replace('_', ' ')}</h3>
                  <p className="approval-description">{selectedApproval.description}</p>

                  {selectedApproval.details && (
                    <pre className="approval-details">
                      {JSON.stringify(selectedApproval.details, null, 2)}
                    </pre>
                  )}

                  <div className="approval-actions">
                    <button
                      className="btn btn-primary"
                      onClick={handleApprove}
                      disabled={isLoading}
                    >
                      Approve
                    </button>

                    {!showDenyInput ? (
                      <button
                        className="btn btn-danger"
                        onClick={() => setShowDenyInput(true)}
                        disabled={isLoading}
                      >
                        Deny
                      </button>
                    ) : (
                      <div className="deny-input-group">
                        <input
                          type="text"
                          className="form-input"
                          placeholder="Reason (optional)"
                          value={denyReason}
                          onChange={(e) => setDenyReason(e.target.value)}
                        />
                        <button
                          className="btn btn-danger"
                          onClick={handleDeny}
                          disabled={isLoading}
                        >
                          Confirm Deny
                        </button>
                        <button
                          className="btn"
                          onClick={() => {
                            setShowDenyInput(false);
                            setDenyReason('');
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
