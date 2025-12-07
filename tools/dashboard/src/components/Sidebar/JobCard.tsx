import type { Job } from '../../types';

interface JobCardProps {
  job: Job;
  isSelected: boolean;
  onClick: () => void;
}

const STATUS_COLORS: Record<string, string> = {
  queued: 'var(--text-secondary)',
  running: 'var(--accent-blue)',
  succeeded: 'var(--accent-green)',
  failed: 'var(--accent-red)',
  cancelled: 'var(--text-muted)',
  waiting_approval: 'var(--accent-yellow)',
  paused: 'var(--accent-orange)',
  timed_out: 'var(--accent-red)',
  stalled: 'var(--accent-orange)',
};

function formatTimeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

function truncateTask(task: string | undefined, maxLength = 60): string {
  if (!task) return 'Untitled job';
  if (task.length <= maxLength) return task;
  return task.slice(0, maxLength - 3) + '...';
}

export function JobCard({ job, isSelected, onClick }: JobCardProps) {
  const statusColor = STATUS_COLORS[job.status] ?? 'var(--text-secondary)';
  // Task can be in job.task or job.params.task depending on API version
  const task = job.task || job.params?.task;

  return (
    <div className={`job-card ${isSelected ? 'selected' : ''}`} onClick={onClick}>
      <div className="job-card-header">
        <span
          className="job-status-badge"
          style={{ backgroundColor: statusColor }}
        >
          {job.status.replace('_', ' ')}
        </span>
        <span className="job-time">{formatTimeAgo(job.created_at)}</span>
      </div>

      <div className="job-card-task">{truncateTask(task)}</div>

      <div className="job-card-footer">
        <span className="job-id">{job.id.slice(0, 8)}</span>
        {job.current_phase && (
          <span className="job-phase">{job.current_phase}</span>
        )}
        {job.execution_mode === 'hitl' && (
          <span className="job-mode-badge">HITL</span>
        )}
      </div>
    </div>
  );
}
