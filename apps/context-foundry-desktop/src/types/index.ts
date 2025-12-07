// ============================================================================
// Daemon Types
// ============================================================================

export interface DaemonStatus {
  running: boolean
  port: number
  pid?: number
  uptime_seconds?: number
  jobs_running?: number
  jobs_total?: number
  version?: string
}

// ============================================================================
// Job Types
// ============================================================================

export type JobStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled'

export interface Job {
  id: string
  task: string
  working_directory: string
  status: JobStatus
  current_phase?: string
  progress?: number
  created_at: string
  started_at?: string
  completed_at?: string
  error?: string
  artifacts?: string[]
}

export interface JobListResponse {
  jobs: Job[]
  total: number
  limit: number
  offset: number
}

// ============================================================================
// Job Tree Types (Phases and Tasks)
// ============================================================================

export interface TaskNode {
  id: string
  name: string
  status: JobStatus
  started_at?: string
  completed_at?: string
  duration_seconds?: number
  output?: string
}

export interface PhaseNode {
  name: string
  status: JobStatus
  tasks: TaskNode[]
  started_at?: string
  completed_at?: string
}

export interface JobTree {
  job_id: string
  phases: PhaseNode[]
}

// ============================================================================
// Job Timeline Types
// ============================================================================

export interface TimelineEvent {
  timestamp: string
  type: 'phase_start' | 'phase_end' | 'task_start' | 'task_end' | 'error' | 'info'
  phase?: string
  task?: string
  message?: string
  details?: Record<string, unknown>
}

export interface JobTimeline {
  job_id: string
  events: TimelineEvent[]
}

// ============================================================================
// Metrics Types
// ============================================================================

export interface Metrics {
  jobs_total: number
  jobs_running: number
  jobs_pending: number
  jobs_succeeded: number
  jobs_failed: number
  jobs_cancelled: number
  avg_duration_seconds?: number
  success_rate?: number
  uptime_seconds: number
  memory_usage_mb?: number
  cpu_percent?: number
}

// ============================================================================
// Health Types
// ============================================================================

export interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy'
  uptime_seconds: number
  pid: number
  jobs_running: number
  jobs_completed: number
  jobs_failed: number
  jobs_pending: number
  version?: string
}

// ============================================================================
// API Error Types
// ============================================================================

export interface ApiError {
  message: string
  status?: number
  code?: string
}
