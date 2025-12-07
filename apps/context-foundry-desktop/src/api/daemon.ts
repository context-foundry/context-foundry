/**
 * Daemon API Client
 *
 * Provides functions to communicate with the Tauri backend,
 * which in turn communicates with the CF Daemon HTTP API.
 */

import { invoke } from '@tauri-apps/api/core'
import type {
  DaemonStatus,
  HealthResponse,
  JobListResponse,
  Job,
  JobTree,
  JobTimeline,
  Metrics,
} from '../types'

// ============================================================================
// Daemon Management
// ============================================================================

/**
 * Check the current status of the daemon
 */
export async function checkDaemonStatus(): Promise<DaemonStatus> {
  return invoke<DaemonStatus>('check_daemon_status')
}

/**
 * Start the daemon if not already running
 */
export async function startDaemon(): Promise<DaemonStatus> {
  return invoke<DaemonStatus>('start_daemon')
}

/**
 * Stop the daemon
 */
export async function stopDaemon(): Promise<void> {
  return invoke<void>('stop_daemon')
}

/**
 * Restart the daemon
 */
export async function restartDaemon(): Promise<DaemonStatus> {
  return invoke<DaemonStatus>('restart_daemon')
}

// ============================================================================
// Health & Metrics
// ============================================================================

/**
 * Get health information from the daemon
 */
export async function getHealth(): Promise<HealthResponse> {
  return invoke<HealthResponse>('get_health')
}

/**
 * Get metrics from the daemon
 */
export async function getMetrics(): Promise<Metrics> {
  return invoke<Metrics>('get_metrics')
}

// ============================================================================
// Jobs
// ============================================================================

export interface GetJobsOptions {
  status?: string
  limit?: number
  offset?: number
}

/**
 * Get list of jobs with optional filters
 */
export async function getJobs(options: GetJobsOptions = {}): Promise<JobListResponse> {
  return invoke<JobListResponse>('get_jobs', {
    status: options.status,
    limit: options.limit,
    offset: options.offset,
  })
}

/**
 * Get a specific job by ID
 */
export async function getJob(jobId: string): Promise<Job> {
  return invoke<Job>('get_job', { jobId })
}

/**
 * Get job tree (phases and tasks hierarchy)
 */
export async function getJobTree(jobId: string): Promise<JobTree> {
  return invoke<JobTree>('get_job_tree', { jobId })
}

/**
 * Get job timeline (chronological events)
 */
export async function getJobTimeline(jobId: string): Promise<JobTimeline> {
  return invoke<JobTimeline>('get_job_timeline', { jobId })
}

/**
 * Get job phase gates
 */
export async function getJobGates(jobId: string): Promise<unknown> {
  return invoke('get_job_gates', { jobId })
}

// ============================================================================
// Events
// ============================================================================

/**
 * Get recent events across all jobs
 */
export async function getRecentEvents(eventType?: string): Promise<unknown> {
  return invoke('get_recent_events', { eventType })
}

// ============================================================================
// Configuration
// ============================================================================

/**
 * Get daemon configuration
 */
export async function getConfig(): Promise<unknown> {
  return invoke('get_config')
}

/**
 * Get agent configuration
 */
export async function getAgents(): Promise<unknown> {
  return invoke('get_agents')
}
