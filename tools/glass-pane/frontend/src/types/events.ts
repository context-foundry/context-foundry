/**
 * Server-Sent Events (SSE) types for Glass Pane frontend.
 */

import { Log } from './api'

export type SSEEventType =
  | 'phase_update'
  | 'file_created'
  | 'log_batch'
  | 'metrics_update'
  | 'job_status_change'
  | 'heartbeat'

export interface PhaseUpdateData {
  phase: string
  status: string
  description: string
}

export interface FileCreatedData {
  path: string
  timestamp: string
}

export interface LogBatchData {
  logs: Log[]
}

export interface MetricsUpdateData {
  tokens_used: number
  duration: number
  files: number
}

export interface JobStatusChangeData {
  status: 'running' | 'completed' | 'failed'
}

export interface HeartbeatData {
  timestamp: string
}

export type SSEEventData =
  | PhaseUpdateData
  | FileCreatedData
  | LogBatchData
  | MetricsUpdateData
  | JobStatusChangeData
  | HeartbeatData

export interface SSEEvent {
  type: SSEEventType
  data: SSEEventData
}

export interface SSEMessage {
  event: string
  data: string
}
