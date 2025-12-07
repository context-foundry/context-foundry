import { useState, useEffect } from 'react';
import { useSelectedJob, useJobsStore } from '../../stores/jobs';
import { PhaseTimeline } from './PhaseTimeline';
import { JobActions } from './JobActions';
import { ConversationView } from './ConversationView';
import { ArtifactEditor } from './ArtifactEditor';

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

function formatStatus(status: string): string {
  return status
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

function formatMode(mode: string | undefined): string {
  if (!mode) return 'Autonomous';
  return mode.charAt(0).toUpperCase() + mode.slice(1).toLowerCase();
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m ${secs}s`;
  }
  return `${minutes}m ${secs}s`;
}

function calculateDuration(startedAt: string | null | undefined, completedAt: string | null | undefined): number {
  if (!startedAt) return 0;

  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();

  return Math.max(0, Math.floor((end - start) / 1000));
}

export function JobDetail() {
  const job = useSelectedJob();
  const { selectedPhase, selectPhase } = useJobsStore();
  const [elapsed, setElapsed] = useState(0);

  const isRunning = job?.status === 'running';
  const hasStarted = !!job?.started_at;

  // Auto-select first phase (Scout) when job is selected
  useEffect(() => {
    if (job && !selectedPhase) {
      selectPhase('scout');
    }
  }, [job?.id, selectedPhase, selectPhase]);

  // Update elapsed time every second while running
  useEffect(() => {
    if (!job) return;

    // Initial calculation
    setElapsed(calculateDuration(job.started_at, job.completed_at));

    // If running, update every second
    if (isRunning && hasStarted) {
      const interval = setInterval(() => {
        setElapsed(calculateDuration(job.started_at, null));
      }, 1000);
      return () => clearInterval(interval);
    }
  }, [job?.id, job?.started_at, job?.completed_at, isRunning, hasStarted]);

  if (!job) {
    return (
      <section className="job-detail">
        <div className="job-detail-empty">
          <h2>No Job Selected</h2>
          <p>Select a job from the sidebar to view details</p>
        </div>
      </section>
    );
  }

  return (
    <section className="job-detail">
      <div className="job-detail-header">
        <div className="job-detail-title">
          <h2>{job.task}</h2>
          <span className="job-detail-id">{job.id}</span>
        </div>
        <div className="job-detail-header-right">
          {hasStarted && (
            <div className={`job-duration ${isRunning ? 'running' : ''}`}>
              <span className="duration-icon">{isRunning ? '⏱' : '✓'}</span>
              <span className="duration-value">{formatDuration(elapsed)}</span>
            </div>
          )}
          <JobActions job={job} />
        </div>
      </div>

      <div className="job-detail-meta">
        <span className="meta-item">
          <strong>Directory:</strong> {job.working_directory || job.params?.working_directory || 'N/A'}
        </span>
        <span className="meta-item">
          <strong>Mode:</strong>{' '}
          <span className={`job-mode-badge mode-${(job.execution_mode || job.params?.execution_mode) === 'hitl' ? 'hitl' : 'autonomous'}`}>
            {formatMode(job.execution_mode || job.params?.execution_mode)}
          </span>
        </span>
        <span className="meta-item">
          <strong>Status:</strong>{' '}
          <span
            className={`job-status-badge status-${job.status}`}
            style={{ backgroundColor: STATUS_COLORS[job.status] || 'var(--text-secondary)' }}
          >
            {formatStatus(job.status)}
          </span>
        </span>
      </div>

      <PhaseTimeline job={job} />

      {selectedPhase ? (
        <div className="job-detail-content">
          <h3>Phase: {selectedPhase}</h3>
          <ConversationView jobId={job.id} phase={selectedPhase} />
          <ArtifactEditor jobId={job.id} phase={selectedPhase} />
        </div>
      ) : (
        <div className="job-detail-content">
          <p className="phase-hint">Select a phase above to view details</p>
        </div>
      )}

      {job.error && (
        <div className="job-error">
          <strong>Error:</strong> {job.error}
        </div>
      )}
    </section>
  );
}
