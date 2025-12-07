/**
 * Jobs Store
 *
 * Manages job list, selected job, and real-time updates via SSE.
 */

import { create } from 'zustand';
import type { Job, JobFilter, JobSort, Phase, SSEEvent, ActivityMetrics } from '../types';
import * as api from '../api/client';
import { getSSEManager } from '../api/sse';

interface JobsState {
  // Data
  jobs: Job[];
  selectedJobId: string | null;
  selectedPhase: Phase | null;
  activityMetrics: ActivityMetrics | null;

  // Filters
  filter: JobFilter;
  sort: JobSort;
  searchQuery: string;

  // UI State
  isLoading: boolean;
  error: string | null;
  isConnected: boolean;

  // Actions
  fetchJobs: () => Promise<void>;
  selectJob: (jobId: string | null) => void;
  selectPhase: (phase: Phase | null) => void;
  setFilter: (filter: JobFilter) => void;
  setSort: (sort: JobSort) => void;
  setSearchQuery: (query: string) => void;
  cancelJob: (jobId: string) => Promise<void>;
  pauseJob: (jobId: string) => Promise<void>;
  resumeJob: (jobId: string) => Promise<void>;
  handleSSEEvent: (event: SSEEvent) => void;
  initSSE: () => () => void;
}

export const useJobsStore = create<JobsState>((set, get) => ({
  // Initial state
  jobs: [],
  selectedJobId: null,
  selectedPhase: null,
  activityMetrics: null,
  filter: 'all',
  sort: 'newest',
  searchQuery: '',
  isLoading: false,
  error: null,
  isConnected: false,

  fetchJobs: async () => {
    const { filter, sort } = get();
    set({ isLoading: true, error: null });

    try {
      const jobs = await api.listJobs({ filter, sort });
      set({ jobs, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch jobs',
        isLoading: false,
      });
    }
  },

  selectJob: (jobId) => {
    set({ selectedJobId: jobId, selectedPhase: null, activityMetrics: null });
  },

  selectPhase: (phase) => {
    set({ selectedPhase: phase });
  },

  setFilter: (filter) => {
    set({ filter });
    get().fetchJobs();
  },

  setSort: (sort) => {
    set({ sort });
    get().fetchJobs();
  },

  setSearchQuery: (query) => {
    set({ searchQuery: query });
  },

  cancelJob: async (jobId) => {
    try {
      await api.cancelJob(jobId);
      get().fetchJobs();
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to cancel job',
      });
    }
  },

  pauseJob: async (jobId) => {
    try {
      await api.pauseJob(jobId);
      get().fetchJobs();
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to pause job',
      });
    }
  },

  resumeJob: async (jobId) => {
    try {
      await api.resumeJob(jobId);
      get().fetchJobs();
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to resume job',
      });
    }
  },

  handleSSEEvent: (event) => {
    const { jobs, selectedJobId } = get();

    switch (event.type) {
      case 'job_update': {
        const updatedJobs = jobs.map((job) =>
          job.id === event.job_id ? { ...job, ...(event.data as Partial<Job>) } : job
        );
        set({ jobs: updatedJobs });
        break;
      }

      case 'phase_update': {
        // Update the phase status in the job
        const updatedJobs = jobs.map((job) => {
          if (job.id !== event.job_id) return job;

          const data = event.data as { phase: Phase; status: string };
          const updatedPhases = (job.phases || []).map((task) =>
            task.phase === data.phase
              ? { ...task, status: data.status as typeof task.status }
              : task
          );

          return { ...job, phases: updatedPhases, current_phase: data.phase };
        });
        set({ jobs: updatedJobs });
        break;
      }

      case 'metrics': {
        // Only update if this is for the selected job
        if (event.job_id === selectedJobId) {
          set({ activityMetrics: event.data as ActivityMetrics });
        }
        break;
      }

      case 'heartbeat':
        // Connection is alive, no state update needed
        break;

      default:
        console.log('[SSE] Unhandled event type:', event.type);
    }
  },

  initSSE: () => {
    const manager = getSSEManager({
      onConnectionChange: (connected) => {
        set({ isConnected: connected });
      },
    });

    manager.connect();
    const unsubscribe = manager.subscribe(get().handleSSEEvent);

    // Return cleanup function
    return () => {
      unsubscribe();
      manager.disconnect();
    };
  },
}));

// Computed selectors
export const useSelectedJob = () => {
  const jobs = useJobsStore((state) => state.jobs);
  const selectedJobId = useJobsStore((state) => state.selectedJobId);
  return jobs.find((job) => job.id === selectedJobId) ?? null;
};

export const useFilteredJobs = () => {
  const jobs = useJobsStore((state) => state.jobs);
  const searchQuery = useJobsStore((state) => state.searchQuery);

  if (!searchQuery.trim()) return jobs;

  const query = searchQuery.toLowerCase();
  return jobs.filter(
    (job) =>
      (job.task || job.params?.task || '').toLowerCase().includes(query) ||
      (job.working_directory || job.params?.working_directory || '').toLowerCase().includes(query) ||
      job.id.toLowerCase().includes(query)
  );
};
