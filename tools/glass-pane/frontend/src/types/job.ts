/**
 * Job-related TypeScript types for Glass Pane frontend.
 */

export enum Phase {
  Scout = 'Scout',
  Architect = 'Architect',
  Builder = 'Builder',
  Test = 'Test',
  Screenshot = 'Screenshot',
  Documentation = 'Documentation',
  Deploy = 'Deploy',
}

export enum PhaseStatus {
  Pending = 'pending',
  Active = 'active',
  Completed = 'completed',
  Failed = 'failed',
}

export interface PhaseInfo {
  phase: Phase
  status: PhaseStatus
  description: string
  started_at: string | null
  completed_at: string | null
  iteration: number
}

export interface Job {
  id: string
  status: 'running' | 'succeeded' | 'failed' | 'cancelled'
  started_at: string // ISO 8601
  completed_at: string | null
  project_name: string
  current_phase: Phase | null
  tokens_used: number
  total_files: number
}

export interface JobDetail extends Job {
  phases: PhaseInfo[]
}

export interface JobListResponse {
  jobs: Job[]
  total: number
  limit: number
  offset: number
}

// File tree node type
export interface FileNode {
  path: string;           // Full path from root (e.g., "/src/App.tsx")
  name: string;           // File/directory name only (e.g., "App.tsx")
  type: 'file' | 'directory';
  children?: FileNode[];  // Only present for directories
  expanded: boolean;      // UI state for directory expansion
  created_at?: string;    // Optional timestamp
  size?: number;          // Optional file size in bytes
}

// Log entry type
export interface LogEntry {
  id: number;             // Numeric ID
  job_id: string;
  timestamp: string;      // ISO 8601 format
  level: LogLevel;
  message: string;
  source?: string;        // Optional: which service logged this
}

// Log level enum
export enum LogLevel {
  DEBUG = 'DEBUG',
  INFO = 'INFO',
  WARNING = 'WARNING',
  ERROR = 'ERROR'
}

// Phase update data (for SSE events)
export interface PhaseUpdateData {
  phase: string;
  status: 'starting' | 'in_progress' | 'completed' | 'failed';
  message?: string;
  timestamp: string;
}

// File created event data (for SSE events)
export interface FileCreatedData {
  path: string;
  type: 'file' | 'directory';
  timestamp: string;
}

// Token update event data (for SSE events)
export interface TokenUpdateData {
  tokens_used: number;
  total_tokens: number;
  percentage: number;
  timestamp: string;
}

// SSE event union type
export type SSEEventData =
  | { type: 'phase_update'; data: PhaseUpdateData }
  | { type: 'file_created'; data: FileCreatedData }
  | { type: 'log'; data: LogEntry }
  | { type: 'tokens'; data: TokenUpdateData };
