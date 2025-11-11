/**
 * REST API client for MCP Log Monitor
 */

const API_BASE = '/api';

export async function fetchServers() {
  const response = await fetch(`${API_BASE}/servers`);
  if (!response.ok) {
    throw new Error('Failed to fetch servers');
  }
  return response.json();
}

export async function fetchHealth() {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) {
    throw new Error('Health check failed');
  }
  return response.json();
}
