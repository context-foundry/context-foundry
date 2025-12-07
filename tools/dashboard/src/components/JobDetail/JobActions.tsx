import { useJobsStore } from '../../stores/jobs';
import type { Job } from '../../types';

interface JobActionsProps {
  job: Job;
}

export function JobActions({ job }: JobActionsProps) {
  const { cancelJob, pauseJob, resumeJob } = useJobsStore();

  const canCancel = ['queued', 'running', 'paused', 'waiting_approval'].includes(job.status);
  const canPause = job.status === 'running';
  const canResume = job.status === 'paused';

  return (
    <div className="job-actions">
      {canPause && (
        <button className="btn" onClick={() => pauseJob(job.id)}>
          Pause
        </button>
      )}
      {canResume && (
        <button className="btn btn-primary" onClick={() => resumeJob(job.id)}>
          Resume
        </button>
      )}
      {canCancel && (
        <button className="btn btn-danger" onClick={() => cancelJob(job.id)}>
          Cancel
        </button>
      )}
    </div>
  );
}
