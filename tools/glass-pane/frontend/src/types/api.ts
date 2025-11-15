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
}
