import { useEffect } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { JobDetail } from './components/JobDetail';
import { SettingsPanel } from './components/Settings';
import { ApprovalModal } from './components/Approvals';
import { ActivityPanel } from './components/Activity';
import { SidekickModal } from './components/Sidekick';
import { useJobsStore } from './stores/jobs';
import { useApprovalsStore } from './stores/approvals';
import { useSettingsStore } from './stores/settings';
import { useSidekickStore } from './stores/sidekick';

function App() {
  const { fetchJobs, initSSE } = useJobsStore();
  const { fetchApprovals, showModal: showApprovalModal } = useApprovalsStore();
  const { showSettingsPanel } = useSettingsStore();
  const { isOpen: showSidekickModal } = useSidekickStore();

  // Track if activity panel is visible (could be a store or local state)
  const showActivityPanel = false; // TODO: Add toggle

  useEffect(() => {
    // Initial data fetch
    fetchJobs();
    fetchApprovals();

    // Initialize SSE connection (for real-time updates when available)
    const cleanup = initSSE();

    // Poll for jobs every 3 seconds
    const jobsInterval = setInterval(fetchJobs, 3000);

    // Poll for approvals every 5 seconds
    const approvalInterval = setInterval(fetchApprovals, 5000);

    return () => {
      cleanup();
      clearInterval(jobsInterval);
      clearInterval(approvalInterval);
    };
  }, [fetchJobs, fetchApprovals, initSSE]);

  return (
    <div className="app">
      <Header />

      <main className={`main ${showActivityPanel ? 'with-activity-panel' : ''}`}>
        <Sidebar />
        <JobDetail />
        {showActivityPanel && <ActivityPanel />}
      </main>

      {/* Modals */}
      {showApprovalModal && <ApprovalModal />}
      {showSettingsPanel && <SettingsPanel />}
      {showSidekickModal && <SidekickModal />}
    </div>
  );
}

export default App;
