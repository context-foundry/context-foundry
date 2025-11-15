import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { Job } from '../types/job';

interface JobContextValue {
  currentJob: Job | null;
  setCurrentJob: (job: Job | null) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  error: string | null;
  setError: (error: string | null) => void;
  refreshJob: () => Promise<void>;
}

const JobContext = createContext<JobContextValue | undefined>(undefined);

export function JobProvider({ children }: { children: ReactNode }) {
  const [currentJob, setCurrentJob] = useState<Job | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshJob = useCallback(async () => {
    if (!currentJob?.id) return;

    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/jobs/${currentJob.id}`);

      if (!response.ok) {
        throw new Error(`Failed to fetch job: ${response.statusText}`);
      }

      const data = await response.json() as Job;
      setCurrentJob(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      console.error('Error refreshing job:', err);
    } finally {
      setIsLoading(false);
    }
  }, [currentJob?.id]);

  return (
    <JobContext.Provider
      value={{
        currentJob,
        setCurrentJob,
        isLoading,
        setIsLoading,
        error,
        setError,
        refreshJob,
      }}
    >
      {children}
    </JobContext.Provider>
  );
}

export function useJob() {
  const context = useContext(JobContext);
  if (context === undefined) {
    throw new Error('useJob must be used within a JobProvider');
  }
  return context;
}
