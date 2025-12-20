// Job and Task Types
export type JobStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'waiting_approval'
  | 'paused'
  | 'timed_out'
  | 'stalled';

export type TaskStatus =
  | 'created'
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'timed_out';

export type Phase =
  | 'scout'
  | 'architect'
  | 'builder'
  | 'test'
  | 'screenshot'
  | 'documentation'
  | 'deploy'
  | 'feedback';

export type ExecutionMode = 'autonomous' | 'hitl' | 'interactive';

/** Status of a phase in the HITL workflow */
export type PhaseStatus = 'waiting' | 'running' | 'pending_approval' | 'approved' | 'complete' | 'failed';

export interface Job {
  id: string;
  task?: string;
  working_directory?: string;
  status: JobStatus;
  execution_mode?: ExecutionMode;
  current_phase?: Phase | null;
  phases?: Task[];
  expected_phases?: Phase[];  // Phases this job will run (Issue #191)
  created_at: string;
  updated_at?: string;
  started_at?: string | null;
  completed_at?: string | null;
  error?: string | null;
  retry_count?: number;
  max_retries?: number;
  timeout_minutes?: number;
  // API also returns these fields
  params?: {
    task?: string;
    working_directory?: string;
    execution_mode?: string;
    project_name?: string;
    target_phases?: string[];  // Phase selection (Issue #191)
    build_profile?: string;    // Phase selection (Issue #191)
    simple_mode?: boolean;     // Legacy mode (deprecated)
  };
  phase?: string;
  type?: string;
}

export interface Task {
  id: string;
  job_id: string;
  phase: Phase;
  status: TaskStatus;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  mcp_task_id: string | null;
  heartbeat_at: string | null;
}

// Approval Types
export interface PendingApproval {
  id: string;
  job_id: string;
  phase: Phase;
  approval_type: 'phase_transition' | 'tool_call' | 'manual';
  description: string;
  details: Record<string, unknown>;
  created_at: string;
}

// Artifact Types
export interface Artifact {
  id: string;
  job_id: string;
  phase: Phase;
  type: 'code' | 'document' | 'config' | 'other';
  path: string;
  content: string;
  language: string | null;
  created_at: string;
  updated_at: string;
}

// Activity Types (real-time metrics)
export interface ActivityMetrics {
  input_tokens: number;
  output_tokens: number;
  context_percent: number;
  current_action: string | null;
  tool_calls: ToolCall[];
  thoughts: string[];
}

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  result: string | null;
  timestamp: string;
}

// Conversation Types
export interface ConversationMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  tool_calls?: ToolCall[];
}

// SSE Event Types
export type SSEEventType =
  | 'job_created'
  | 'job_started'
  | 'job_update'
  | 'job_completed'
  | 'job_failed'
  | 'phase_update'
  | 'log'
  | 'metrics'
  | 'approval'
  | 'heartbeat';

export interface SSEEvent {
  type: SSEEventType;
  job_id: string;
  data: unknown;
  timestamp: string;
}

export interface JobUpdateEvent extends SSEEvent {
  type: 'job_update';
  data: Partial<Job>;
}

export interface PhaseUpdateEvent extends SSEEvent {
  type: 'phase_update';
  data: {
    phase: Phase;
    status: TaskStatus;
    message?: string;
  };
}

export interface LogEvent extends SSEEvent {
  type: 'log';
  data: {
    level: 'debug' | 'info' | 'warning' | 'error';
    message: string;
    phase?: Phase;
  };
}

export interface MetricsEvent extends SSEEvent {
  type: 'metrics';
  data: ActivityMetrics;
}

// Settings Types
export interface TeamSettings {
  team_id: string | null;
  s3_bucket: string | null;
  s3_prefix: string;
  s3_region: string;
  aws_profile: string | null;
  sync_mode: 'team' | 'local-only';
}

export interface DaemonSettings {
  poll_interval: number;
  max_concurrent_jobs: number;
  log_level: 'debug' | 'info' | 'warning' | 'error';
  dashboard_port: number;
}

// Filter and Sort Types
export type JobFilter = 'all' | JobStatus;
export type JobSort = 'newest' | 'oldest' | 'status';
