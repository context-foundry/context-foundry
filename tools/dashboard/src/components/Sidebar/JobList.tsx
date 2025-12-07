import { useJobsStore, useFilteredJobs } from '../../stores/jobs';
import { JobCard } from './JobCard';

export function JobList() {
  const { selectedJobId, selectJob, isLoading, error } = useJobsStore();
  const jobs = useFilteredJobs();

  if (isLoading && jobs.length === 0) {
    return (
      <div className="job-list">
        <div className="job-list-loading">Loading jobs...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="job-list">
        <div className="job-list-error">{error}</div>
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="job-list">
        <div className="job-list-empty">No jobs found</div>
      </div>
    );
  }

  return (
    <div className="job-list">
      {jobs.map((job) => (
        <JobCard
          key={job.id}
          job={job}
          isSelected={job.id === selectedJobId}
          onClick={() => selectJob(job.id)}
        />
      ))}
    </div>
  );
}
