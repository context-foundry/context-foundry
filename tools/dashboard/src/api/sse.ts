/**
 * SSE (Server-Sent Events) Connection Manager
 *
 * Handles real-time event streaming from CF Daemon.
 * Supports automatic reconnection with exponential backoff.
 */

import type { SSEEvent } from '../types';

export type SSEHandler = (event: SSEEvent) => void;
export type ConnectionStateHandler = (connected: boolean) => void;

interface SSEManagerOptions {
  url?: string;
  reconnectDelay?: number;
  maxReconnectDelay?: number;
  onConnectionChange?: ConnectionStateHandler;
}

const DEFAULT_OPTIONS: Required<Omit<SSEManagerOptions, 'onConnectionChange'>> = {
  url: '/events',
  reconnectDelay: 3000,
  maxReconnectDelay: 30000,
};

export class SSEManager {
  private eventSource: EventSource | null = null;
  private handlers: Map<string, Set<SSEHandler>> = new Map();
  private globalHandlers: Set<SSEHandler> = new Set();
  private reconnectAttempts = 0;
  private reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
  private options: Required<Omit<SSEManagerOptions, 'onConnectionChange'>>;
  private onConnectionChange?: ConnectionStateHandler;
  private _isConnected = false;

  constructor(options: SSEManagerOptions = {}) {
    this.options = { ...DEFAULT_OPTIONS, ...options };
    this.onConnectionChange = options.onConnectionChange;
  }

  get isConnected(): boolean {
    return this._isConnected;
  }

  /**
   * Connect to the SSE endpoint
   */
  connect(): void {
    if (this.eventSource) {
      return;
    }

    this.eventSource = new EventSource(this.options.url);

    this.eventSource.onopen = () => {
      console.log('[SSE] Connected');
      this.reconnectAttempts = 0;
      this._isConnected = true;
      this.onConnectionChange?.(true);
    };

    this.eventSource.onmessage = (event) => {
      try {
        const data: SSEEvent = JSON.parse(event.data);
        this.dispatchEvent(data);
      } catch (error) {
        console.error('[SSE] Failed to parse event:', error);
      }
    };

    this.eventSource.onerror = () => {
      // Only log on first failure, then silently retry
      if (this.reconnectAttempts === 0) {
        console.log('[SSE] Not available, falling back to polling');
      }
      this._isConnected = false;
      this.onConnectionChange?.(false);
      this.scheduleReconnect();
    };
  }

  /**
   * Disconnect from the SSE endpoint
   */
  disconnect(): void {
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    this._isConnected = false;
    this.onConnectionChange?.(false);
  }

  /**
   * Subscribe to events for a specific job
   */
  subscribeToJob(jobId: string, handler: SSEHandler): () => void {
    if (!this.handlers.has(jobId)) {
      this.handlers.set(jobId, new Set());
    }
    this.handlers.get(jobId)!.add(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.handlers.get(jobId);
      if (handlers) {
        handlers.delete(handler);
        if (handlers.size === 0) {
          this.handlers.delete(jobId);
        }
      }
    };
  }

  /**
   * Subscribe to all events (global handler)
   */
  subscribe(handler: SSEHandler): () => void {
    this.globalHandlers.add(handler);
    return () => {
      this.globalHandlers.delete(handler);
    };
  }

  private dispatchEvent(event: SSEEvent): void {
    // Dispatch to job-specific handlers
    const jobHandlers = this.handlers.get(event.job_id);
    if (jobHandlers) {
      jobHandlers.forEach((handler) => handler(event));
    }

    // Dispatch to global handlers
    this.globalHandlers.forEach((handler) => handler(event));
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimeout) {
      return;
    }

    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    // Exponential backoff with jitter
    const delay = Math.min(
      this.options.reconnectDelay * Math.pow(2, this.reconnectAttempts) +
        Math.random() * 1000,
      this.options.maxReconnectDelay
    );

    // Only log reconnect attempts at debug level after first failure
    if (this.reconnectAttempts < 3) {
      console.debug(`[SSE] Retry in ${Math.round(delay / 1000)}s...`);
    }

    this.reconnectTimeout = setTimeout(() => {
      this.reconnectTimeout = null;
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }
}

// Singleton instance
let sseManager: SSEManager | null = null;

export function getSSEManager(options?: SSEManagerOptions): SSEManager {
  if (!sseManager) {
    sseManager = new SSEManager(options);
  }
  return sseManager;
}

export function resetSSEManager(): void {
  if (sseManager) {
    sseManager.disconnect();
    sseManager = null;
  }
}
