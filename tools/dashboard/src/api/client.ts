/**
 * API Client for Context Foundry Daemon
 *
 * Handles all HTTP communication with the CF Daemon backend.
 * Supports authentication via X-CF-Auth header.
 */

// Detect if running in Tauri
// @ts-ignore
const isTauri = typeof window !== 'undefined' && window.__TAURI__ !== undefined;

// In Tauri, the API is at localhost:8421 (daemon port)
// In Web (dev/prod), we use relative paths (proxied by Vite or served by daemon)
export const API_BASE = isTauri ? 'http://127.0.0.1:8421' : '';

console.log('Context Foundry API Client Initialized:', { isTauri, API_BASE });

let authToken: string | null = null;

/**
 * Set the authentication token for API requests
 */
export function setAuthToken(token: string): void {
  authToken = token;
}

/**
 * Get the current auth token (fetches from daemon if not set)
 */
export async function getAuthToken(): Promise<string | null> {
  if (authToken) return authToken;

  try {
    // Auth token endpoint only works from localhost
    const response = await fetch('http://127.0.0.1:8420/auth-token');
    if (response.ok) {
      const data = await response.json();
      authToken = data.token;
      return authToken;
    }
  } catch {
    console.warn('Failed to fetch auth token - running without authentication');
  }
  return null;
}

/**
 * Make an authenticated fetch request
 */
async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const token = await getAuthToken();

  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');
  if (token) {
    headers.set('X-CF-Auth', token);
  }

  return fetch(`${API_BASE}${url}`, {
    ...options,
    headers,
  });
}

// ============ Status Endpoints ============

export interface DaemonStatus {
  status: 'running' | 'stopped';
  version: string;
  uptime_seconds: number;
  jobs: {
    total: number;
    running: number;
    queued: number;
    succeeded: number;
    failed: number;
  };
}

export async function getStatus(): Promise<DaemonStatus> {
  const response = await fetchWithAuth('/status');
  if (!response.ok) {
    throw new Error(`Failed to get status: ${response.statusText}`);
  }
  return response.json();
}

// ============ Job Endpoints ============

import type { Job, JobFilter, JobSort } from '../types';

export interface ListJobsParams {
  filter?: JobFilter;
  sort?: JobSort;
  limit?: number;
  offset?: number;
}

// Transform API response to match frontend Job type
// API returns job_id, frontend expects id
function transformJob(apiJob: Record<string, unknown>): Job {
  return {
    ...apiJob,
    id: (apiJob.job_id || apiJob.id) as string,
  } as Job;
}

export async function listJobs(params: ListJobsParams = {}): Promise<Job[]> {
  const searchParams = new URLSearchParams();
  if (params.filter && params.filter !== 'all') {
    searchParams.set('status', params.filter);
  }
  if (params.sort) {
    searchParams.set('sort', params.sort);
  }
  if (params.limit) {
    searchParams.set('limit', String(params.limit));
  }
  if (params.offset) {
    searchParams.set('offset', String(params.offset));
  }

  const query = searchParams.toString();
  const url = query ? `/api/jobs?${query}` : '/api/jobs';

  const response = await fetchWithAuth(url);
  if (!response.ok) {
    throw new Error(`Failed to list jobs: ${response.statusText}`);
  }
  const data = await response.json();
  // API returns { jobs: [...], summary: {...} } - extract just the jobs array
  const jobs = data.jobs || data;
  // Transform job_id -> id for frontend compatibility
  return jobs.map(transformJob);
}

export async function getJob(jobId: string): Promise<Job> {
  const response = await fetchWithAuth(`/api/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error(`Failed to get job: ${response.statusText}`);
  }
  const data = await response.json();
  return transformJob(data);
}

export async function cancelJob(jobId: string): Promise<void> {
  const response = await fetchWithAuth(`/api/jobs/${jobId}/cancel`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`Failed to cancel job: ${response.statusText}`);
  }
}

export async function pauseJob(jobId: string): Promise<void> {
  const response = await fetchWithAuth(`/api/jobs/${jobId}/pause`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`Failed to pause job: ${response.statusText}`);
  }
}

export async function resumeJob(jobId: string): Promise<void> {
  const response = await fetchWithAuth(`/api/jobs/${jobId}/resume`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`Failed to resume job: ${response.statusText}`);
  }
}

// ============ Approval Endpoints ============

import type { PendingApproval } from '../types';

export async function getPendingApprovals(): Promise<PendingApproval[]> {
  const response = await fetchWithAuth('/api/pending-approvals');
  if (!response.ok) {
    throw new Error(`Failed to get pending approvals: ${response.statusText}`);
  }
  return response.json();
}

export async function approveAction(approvalId: string): Promise<void> {
  const response = await fetchWithAuth('/approve', {
    method: 'POST',
    body: JSON.stringify({ approval_id: approvalId }),
  });
  if (!response.ok) {
    throw new Error(`Failed to approve: ${response.statusText}`);
  }
}

export async function denyAction(approvalId: string, reason?: string): Promise<void> {
  const response = await fetchWithAuth('/deny', {
    method: 'POST',
    body: JSON.stringify({ approval_id: approvalId, reason }),
  });
  if (!response.ok) {
    throw new Error(`Failed to deny: ${response.statusText}`);
  }
}

export async function resumePipeline(jobId: string): Promise<void> {
  const response = await fetchWithAuth('/resume-pipeline', {
    method: 'POST',
    body: JSON.stringify({ job_id: jobId }),
  });
  if (!response.ok) {
    throw new Error(`Failed to resume pipeline: ${response.statusText}`);
  }
}

// ============ Phase Handoff Endpoints (HITL) ============

import type { PhaseStatus } from '../types';
export type { PhaseStatus };

/** Handoff data for a single phase */
export interface PhaseHandoff {
  /** Output file name (e.g., "scout-report.md") */
  output: string | null;
  /** Markdown content of the handoff file */
  content: string | null;
  /** Current status of this phase */
  status: PhaseStatus;
  /** When the phase was approved (ISO timestamp) */
  approved_at?: string;
  /** Who approved the phase */
  approved_by?: string;
}

/** Response from GET /phase-prompts (now returns handoffs) */
export interface PhaseHandoffsResponse {
  /** Map of phase name to handoff data */
  handoffs: Record<string, PhaseHandoff>;
  /** Full status object */
  status: {
    execution_mode: string;
    created_at?: string;
    phases: Record<string, { status: PhaseStatus; [key: string]: unknown }>;
  };
  /** Execution mode (autonomous, hitl, interactive) */
  execution_mode: string;
}

/**
 * Get phase handoffs for a job (HITL review).
 * Returns the .md handoff files that humans review before approving.
 */
export async function getPhaseHandoffs(jobId: string): Promise<PhaseHandoffsResponse> {
  const response = await fetchWithAuth(`/phase-prompts?job_id=${jobId}`);
  if (!response.ok) {
    throw new Error(`Failed to get phase handoffs: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Approve a phase to proceed (HITL mode).
 * In HITL mode, agents wait for approval of the previous phase's handoff
 * before starting the next phase.
 */
export async function approvePhase(jobId: string, phase: string): Promise<void> {
  const response = await fetchWithAuth('/phase-acknowledge', {
    method: 'POST',
    body: JSON.stringify({ job_id: jobId, phase }),
  });
  if (!response.ok) {
    throw new Error(`Failed to approve phase: ${response.statusText}`);
  }
}

/**
 * Get phases that are pending approval.
 * Convenience function to filter handoffs by status.
 */
export function getPhasesPendingApproval(handoffs: PhaseHandoffsResponse): string[] {
  return Object.entries(handoffs.handoffs)
    .filter(([_, data]) => data.status === 'pending_approval')
    .map(([phase]) => phase);
}

// ============ Artifact Endpoints ============

import type { Artifact } from '../types';

export async function getArtifact(jobId: string, artifactId: string): Promise<Artifact> {
  const response = await fetchWithAuth(`/artifact?job_id=${jobId}&artifact_id=${artifactId}`);
  if (!response.ok) {
    throw new Error(`Failed to get artifact: ${response.statusText}`);
  }
  return response.json();
}

export async function updateArtifact(
  jobId: string,
  artifactId: string,
  content: string
): Promise<void> {
  const response = await fetchWithAuth('/artifact', {
    method: 'POST',
    body: JSON.stringify({
      job_id: jobId,
      artifact_id: artifactId,
      content,
    }),
  });
  if (!response.ok) {
    throw new Error(`Failed to update artifact: ${response.statusText}`);
  }
}

// ============ Sidekick Chat ============

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export async function sendChatMessage(
  jobId: string,
  message: string,
  history: ChatMessage[] = []
): Promise<string> {
  const response = await fetchWithAuth('/api/sidekick-chat', {
    method: 'POST',
    body: JSON.stringify({
      job_id: jobId,
      message,
      history,
    }),
  });
  if (!response.ok) {
    throw new Error(`Failed to send chat message: ${response.statusText}`);
  }
  const data = await response.json();
  return data.response;
}

// ============ Conversation & Artifacts ============

import type { ConversationMessage } from '../types';

export interface ConversationResponse {
  job_id: string;
  phase: string;
  messages: ConversationMessage[];
}

export async function getJobConversation(jobId: string, phase: string): Promise<ConversationMessage[]> {
  const response = await fetchWithAuth(`/api/jobs/${jobId}/conversation?phase=${phase}`);
  if (!response.ok) {
    throw new Error(`Failed to get conversation: ${response.statusText}`);
  }
  const data: ConversationResponse = await response.json();
  return data.messages || [];
}

export interface ArtifactData {
  name: string;
  path: string;
  type: string;
  content: string;
  size: number;
}

export interface ArtifactsResponse {
  job_id: string;
  phase: string;
  artifacts: ArtifactData[];
}

export async function getJobArtifacts(jobId: string, phase: string): Promise<ArtifactData[]> {
  const response = await fetchWithAuth(`/api/jobs/${jobId}/artifacts?phase=${phase}`);
  if (!response.ok) {
    throw new Error(`Failed to get artifacts: ${response.statusText}`);
  }
  const data: ArtifactsResponse = await response.json();
  return data.artifacts || [];
}

// ============ Settings Endpoints ============

import type { TeamSettings, DaemonSettings } from '../types';

export async function getTeamSettings(): Promise<TeamSettings> {
  const response = await fetchWithAuth('/api/settings/team');
  if (!response.ok) {
    throw new Error(`Failed to get team settings: ${response.statusText}`);
  }
  return response.json();
}

export async function updateTeamSettings(settings: Partial<TeamSettings>): Promise<void> {
  const response = await fetchWithAuth('/api/settings/team', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
  if (!response.ok) {
    throw new Error(`Failed to update team settings: ${response.statusText}`);
  }
}

export async function getDaemonSettings(): Promise<DaemonSettings> {
  const response = await fetchWithAuth('/api/settings/daemon');
  if (!response.ok) {
    throw new Error(`Failed to get daemon settings: ${response.statusText}`);
  }
  return response.json();
}

export async function testS3Connection(): Promise<{ success: boolean; message: string }> {
  const response = await fetchWithAuth('/api/settings/test-s3', {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`Failed to test S3 connection: ${response.statusText}`);
  }
  return response.json();
}
