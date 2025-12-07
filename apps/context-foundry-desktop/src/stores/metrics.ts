/**
 * Metrics State Store
 *
 * Manages daemon metrics and health information.
 */

import { create } from 'zustand'
import type { Metrics, HealthResponse } from '../types'
import * as api from '../api/daemon'

interface MetricsSample {
  timestamp: number
  jobsRunning: number
  jobsTotal: number
  cpuPercent?: number
  memoryMb?: number
}

interface MetricsState {
  // State
  metrics: Metrics | null
  health: HealthResponse | null
  history: MetricsSample[]
  isLoading: boolean
  error: string | null

  // Actions
  fetchMetrics: () => Promise<void>
  fetchHealth: () => Promise<void>
  refresh: () => Promise<void>
}

const MAX_HISTORY_SAMPLES = 60 // Keep 60 samples for graphs

export const useMetricsStore = create<MetricsState>((set, get) => ({
  // Initial state
  metrics: null,
  health: null,
  history: [],
  isLoading: false,
  error: null,

  // Fetch metrics
  fetchMetrics: async () => {
    set({ isLoading: true, error: null })

    try {
      const metrics = await api.getMetrics()
      const { history } = get()

      // Add new sample to history
      const newSample: MetricsSample = {
        timestamp: Date.now(),
        jobsRunning: metrics.jobs_running,
        jobsTotal: metrics.jobs_total,
        cpuPercent: metrics.cpu_percent,
        memoryMb: metrics.memory_usage_mb,
      }

      const newHistory = [...history, newSample].slice(-MAX_HISTORY_SAMPLES)

      set({ metrics, history: newHistory, isLoading: false })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch metrics',
        isLoading: false,
      })
    }
  },

  // Fetch health
  fetchHealth: async () => {
    try {
      const health = await api.getHealth()
      set({ health })
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to fetch health',
      })
    }
  },

  // Refresh all metrics data
  refresh: async () => {
    await Promise.all([
      get().fetchMetrics(),
      get().fetchHealth(),
    ])
  },
}))
