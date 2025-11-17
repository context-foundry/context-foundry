/**
 * Type definitions for Forge chat interface
 */

export interface ChatMessage {
  id: number;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  tokens_used?: number;
}

export interface ChatSession {
  id: string;
  created_at: string;
  last_activity: string;
  model: 'sonnet' | 'opus' | 'haiku';
  plan_mode: boolean;
  bypass_permissions: boolean;
  title?: string;
  message_count: number;
}

export interface ChatSessionListResponse {
  sessions: ChatSession[];
  total: number;
  limit: number;
  offset: number;
}

export interface ChatHistoryResponse {
  session: ChatSession;
  messages: ChatMessage[];
}

export interface ChatStreamEvent {
  type: 'delta' | 'complete' | 'error';
  text?: string;
  message?: string;
  session_id?: string;
}

export interface SendMessageRequest {
  session_id?: string;
  message: string;
  model: 'sonnet' | 'opus' | 'haiku';
  plan_mode: boolean;
  bypass_permissions: boolean;
}

export interface CLIStatus {
  available: boolean;
  path?: string;
  version?: string;
  error?: string;
}

export interface StartBuildRequest {
  task: string;
  working_directory: string;
  mode: 'new_project' | 'incremental' | 'existing_repo';
  timeout_minutes: number;
  use_parallel?: boolean;
  github_repo_name?: string;
}

export interface StartBuildResponse {
  success: boolean;
  job_id?: string;
  message: string;
  status?: string;
}
