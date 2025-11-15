import { useEffect, useState } from 'react';
import { useJob } from '../contexts/JobContext';
import { Job } from '../types/job';

type JobFilter = 'all' | 'running' | 'succeeded' | 'failed';

export default function JobSelector() {
  const { currentJob, setCurrentJob, setIsLoading, setError } = useJob();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [filter, setFilter] = useState<JobFilter>('running');

  useEffect(() => {
    fetchJobs();
  }, [filter]);

  const fetchJobs = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (filter !== 'all') {
        params.append('status', filter);
      }
      params.append('limit', '50');

      const response = await fetch(`/api/jobs?${params}`);

      if (!response.ok) {
        throw new Error(`Failed to fetch jobs: ${response.statusText}`);
      }

      const data = await response.json() as { jobs: Job[] };
      setJobs(data.jobs);

      // Auto-select first job if none selected
      if (!currentJob && data.jobs.length > 0) {
        setCurrentJob(data.jobs[0]);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      console.error('Error fetching jobs:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleJobChange = (jobId: string) => {
    const selected = jobs.find(job => job.id === jobId);
    if (selected) {
      setCurrentJob(selected);
    }
  };

  return (
    <div className="flex items-center gap-4">
      {/* Filter Tabs */}
      <div className="flex gap-2">
        {(['running', 'succeeded', 'all'] as JobFilter[]).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1 text-sm rounded-lg transition-colors ${
              filter === f
                ? 'bg-cyan-500 text-white'
                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
            }`}
          >
            {f === 'succeeded' ? 'Completed' : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* Job Dropdown */}
      <select
        value={currentJob?.id || ''}
        onChange={(e) => handleJobChange(e.target.value)}
        className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-gray-100 focus:outline-none focus:ring-2 focus:ring-cyan-500 min-w-[300px]"
      >
        {jobs.length === 0 ? (
          <option value="">No jobs found</option>
        ) : (
          jobs.map(job => (
            <option key={job.id} value={job.id}>
              {job.project_name} - {new Date(job.started_at).toLocaleString()} ({job.status})
            </option>
          ))
        )}
      </select>

      {/* Refresh Button */}
      <button
        onClick={fetchJobs}
        className="p-2 bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"
        title="Refresh jobs"
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
      </button>
    </div>
  );
}
