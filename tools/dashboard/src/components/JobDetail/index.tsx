import { useSelectedJob, useJobsStore } from '../../stores/jobs';
import { PhaseTimeline } from './PhaseTimeline';
import { JobActions } from './JobActions';
import { ConversationView } from './ConversationView';
import { ArtifactEditor } from './ArtifactEditor';

export function JobDetail() {
  const job = useSelectedJob();
  const { selectedPhase } = useJobsStore();

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
        <JobActions job={job} />
      </div>

      <div className="job-detail-meta">
        <span className="meta-item">
          <strong>Directory:</strong> {job.working_directory || job.params?.working_directory || 'N/A'}
        </span>
        <span className="meta-item">
          <strong>Mode:</strong> {(job.execution_mode || job.params?.execution_mode || 'autonomous').toUpperCase()}
        </span>
        <span className="meta-item">
          <strong>Status:</strong> {job.status.replace('_', ' ')}
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
