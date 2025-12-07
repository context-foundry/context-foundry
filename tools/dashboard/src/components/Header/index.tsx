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
        <button className="btn" onClick={openSettings}>
          Settings
        </button>
      </div>
    </header>
  );
}
