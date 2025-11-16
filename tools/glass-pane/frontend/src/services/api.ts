/**
 * Centralized API service with automatic retry and error handling
 */

const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // 1 second

interface FetchOptions extends RequestInit {
  retries?: number;
  retryDelay?: number;
}

async function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Fetch with automatic retry logic
 */
export async function fetchWithRetry(
  url: string,
  options: FetchOptions = {}
): Promise<Response> {
  const { retries = MAX_RETRIES, retryDelay = RETRY_DELAY, ...fetchOptions } = options;

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetch(url, fetchOptions);

      // If successful or client error (4xx), return immediately
      if (response.ok || (response.status >= 400 && response.status < 500)) {
        return response;
      }

      // Server error (5xx) - retry
      lastError = new Error(`HTTP ${response.status}: ${response.statusText}`);

      if (attempt < retries) {
        console.warn(`Request failed (attempt ${attempt + 1}/${retries + 1}): ${url}`, lastError.message);
        await sleep(retryDelay * (attempt + 1)); // Exponential backoff
        continue;
      }
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));

      // Network error - retry
      if (attempt < retries) {
        console.warn(`Network error (attempt ${attempt + 1}/${retries + 1}): ${url}`, lastError.message);
        await sleep(retryDelay * (attempt + 1)); // Exponential backoff
        continue;
      }
    }
  }

  throw lastError || new Error('Request failed after retries');
}

/**
 * Fetch JSON with automatic retry
 */
export async function fetchJSON<T>(
  url: string,
  options: FetchOptions = {}
): Promise<T> {
  const response = await fetchWithRetry(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

/**
 * API endpoints
 */
export const api = {
  // Jobs
  async getJobs(params?: Record<string, string>) {
    const query = params ? '?' + new URLSearchParams(params).toString() : '';
    return fetchJSON<any>(`/api/jobs${query}`);
  },

  async getJob(jobId: string) {
    return fetchJSON<any>(`/api/jobs/${jobId}`);
  },

  async getJobPhases(jobId: string) {
    return fetchJSON<any>(`/api/jobs/${jobId}/phases/detailed`);
  },

  async getJobLogs(jobId: string, limit?: number) {
    const query = limit ? `?limit=${limit}` : '';
    return fetchJSON<any>(`/api/jobs/${jobId}/logs${query}`);
  },

  // Files
  async getFiles(jobId: string) {
    return fetchJSON<any>(`/api/files/list?job_id=${jobId}`);
  },

  async getFileContent(jobId: string, filePath: string) {
    const response = await fetchWithRetry(
      `/api/files/content?job_id=${jobId}&file_path=${encodeURIComponent(filePath)}`
    );
    return response.text();
  },

  // Artifacts
  async getMarkdownFiles(jobId: string) {
    return fetchJSON<any>(`/api/artifacts/${jobId}/markdown`);
  },

  async getMarkdownContent(jobId: string, fileName: string) {
    const response = await fetchWithRetry(
      `/api/artifacts/${jobId}/markdown/${fileName}`
    );
    return response.text();
  },

  // Health check
  async checkHealth() {
    try {
      const response = await fetchWithRetry('/health', { retries: 1 });
      return response.ok;
    } catch {
      return false;
    }
  },
};

/**
 * Health monitor - periodically check if backend is alive
 */
export class HealthMonitor {
  private interval: number | null = null;
  private listeners: Set<(healthy: boolean) => void> = new Set();
  private healthy = true;

  start(intervalMs = 30000) { // Check every 30 seconds
    if (this.interval) return;

    this.checkHealth(); // Initial check

    this.interval = window.setInterval(() => {
      this.checkHealth();
    }, intervalMs);
  }

  stop() {
    if (this.interval) {
      clearInterval(this.interval);
      this.interval = null;
    }
  }

  private async checkHealth() {
    const wasHealthy = this.healthy;
    this.healthy = await api.checkHealth();

    if (wasHealthy !== this.healthy) {
      console.log(`Backend health changed: ${this.healthy ? 'healthy' : 'unhealthy'}`);
      this.notifyListeners();
    }
  }

  private notifyListeners() {
    this.listeners.forEach(listener => listener(this.healthy));
  }

  onHealthChange(listener: (healthy: boolean) => void) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  isHealthy() {
    return this.healthy;
  }
}

export const healthMonitor = new HealthMonitor();
