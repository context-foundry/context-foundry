import { useSettingsStore } from '../../stores/settings';
import { useApprovalCount } from '../../stores/approvals';
import { useApprovalsStore } from '../../stores/approvals';
import { SidekickInput } from '../Sidekick';

export function Header() {
  const { openSettings } = useSettingsStore();
  const { openModal: openApprovals } = useApprovalsStore();
  const approvalCount = useApprovalCount();

  return (
    <header className="header">
      <div className="header-left">
        <div className="logo">
          <span className="logo-text">CF</span>
        </div>
      </div>

      <div className="header-center">
        <SidekickInput />
      </div>

      <div className="header-right">
        {approvalCount > 0 && (
          <button className="btn approval-btn" onClick={openApprovals}>
            Approvals ({approvalCount})
          </button>
        )}
        <button className="icon-btn" onClick={openSettings} title="Settings">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="4" y1="6" x2="20" y2="6" />
            <line x1="4" y1="12" x2="20" y2="12" />
            <line x1="4" y1="18" x2="20" y2="18" />
          </svg>
        </button>
      </div>
    </header>
  );
}
