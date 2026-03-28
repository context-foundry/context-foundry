/**
 * Jobs State Store
 *
 * Manages the list of jobs and provides actions for
 * fetching and filtering jobs.
 */

import { create } from 'zustand'
import type { Job, JobStatus, JobTree, JobTimeline } from '../types'
import * as api from '../api/daemon'

interface JobsState {
  // State
  jobs: Job[]
  selectedJob: Job | null
  selectedJobTree: JobTree | null
  selectedJobTimeline: JobTimeline | null
  isLoading: boolean
  error: string | null

  // Filters
  statusFilter: JobStatus | 'all'
  searchQuery: string

  // Pagination
  total: number
  limit: number
  offset: number

  // Actions
  fetchJobs: () => Promise<void>
  selectJob: (jobId: string) => Promise<void>
  clearSelectedJob: () => void
  setStatusFilter: (status: JobStatus | 'all') => void
  setSearchQuery: (query: string) => void
  refreshJobs: () => Promise<void>
}

export const useJobsStore = create<JobsState>((set, get) => ({
  // Initial state
  jobs: [],
  selectedJob: null,
  selectedJobTree: null,
  selectedJobTimeline: null,
  isLoading: false,
  error: null,

  statusFilter: 'all',
  searchQuery: '',

  total: 0,
  limit: 50,
  offset: 0,

  // Fetch jobs with current filters
  fetchJobs: async () => {
    const { statusFilter, limit, offset } = get()
    set({ isLoading: true, error: null })

    try {
      const response = await api.getJobs({
        status: statusFilter === 'all' ? undefined : statusFilter,
        limit,
        offset,
      })

      set({
        jobs: response.jobs || [],
        total: response.total || 0,
        isLoading: false,
      })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch jobs',
        isLoading: false,
      })
    }
  },

  // Select a job and fetch its details
  selectJob: async (jobId: string) => {
    set({ isLoading: true, error: null })

    try {
      const [job, tree, timeline] = await Promise.all([
        api.getJob(jobId),
        api.getJobTree(jobId).catch(() => null),
        api.getJobTimeline(jobId).catch(() => null),
      ])

      set({
        selectedJob: job,
        selectedJobTree: tree,
        selectedJobTimeline: timeline,
        isLoading: false,
      })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch job details',
        isLoading: false,
      })
    }
  },

  // Clear selected job
  clearSelectedJob: () => {
    set({
      selectedJob: null,
      selectedJobTree: null,
      selectedJobTimeline: null,
    })
  },

  // Set status filter
  setStatusFilter: (status: JobStatus | 'all') => {
    set({ statusFilter: status, offset: 0 })
    get().fetchJobs()
  },

  // Set search query
  setSearchQuery: (query: string) => {
    set({ searchQuery: query })
  },

  // Refresh jobs (called periodically)
  refreshJobs: async () => {
    const { selectedJob } = get()

    // Fetch jobs list
    await get().fetchJobs()

    // If a job is selected, refresh its details too
    if (selectedJob) {
      try {
        const [job, tree, timeline] = await Promise.all([
          api.getJob(selectedJob.id),
          api.getJobTree(selectedJob.id).catch(() => null),
          api.getJobTimeline(selectedJob.id).catch(() => null),
        ])

        set({
          selectedJob: job,
          selectedJobTree: tree,
          selectedJobTimeline: timeline,
        })
      } catch {
        // Job might have been deleted, clear selection
        set({
          selectedJob: null,
          selectedJobTree: null,
          selectedJobTimeline: null,
        })
      }
    }
  },
}))
