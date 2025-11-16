/**
 * API response types for Glass Pane frontend.
 */

export enum LogLevel {
  DEBUG = 'DEBUG',
  INFO = 'INFO',
  WARNING = 'WARNING',
  ERROR = 'ERROR',
}

export interface Log {
  id: number
  job_id: string
  timestamp: string // ISO 8601
  level: LogLevel
  message: string
}

export interface LogListResponse {
  logs: Log[]
  total: number
  limit: number
  offset: number
}

export interface FileContent {
  path: string
  content: string
  size: number
  modified_at: number
}

export interface FileNode {
  path: string
  name: string
  type: 'file' | 'directory'
  children?: FileNode[]
  expanded: boolean
  created_at?: string
}

export interface SessionSummary {
  session_id: string
  project_name: string
  files_created: string[]
  timestamp: string
}

export interface CurrentPhase {
  phase: string
  status: string
  description: string
  timestamp: string
  session_id: string
  iteration: number
  parallel_build_info?: ParallelBuildInfo
}

export interface ParallelBuildInfo {
  parallel_mode: boolean
  total_tasks: number
  current_wave: number
  max_wave: number
  tasks_per_wave: Record<string, number>
  max_concurrent_agents: number
}

export interface ParallelAgent {
  task_id: string
  task_name: string
  description: string
  status: 'in_progress' | 'completed' | 'failed'
  wave: number
  started_at: string
  completed_at?: string
  duration?: number
  files: string[]
  commands_executed?: number
  error?: string
  stderr?: string
}

export interface ParallelAgentsResponse {
  agents: ParallelAgent[]
  has_parallel_build: boolean
}
