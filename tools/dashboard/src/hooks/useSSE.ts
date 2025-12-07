/**
 * React hook for SSE subscriptions
 */

import { useEffect, useCallback } from 'react';
import { getSSEManager, SSEHandler } from '../api/sse';
import type { SSEEvent } from '../types';

/**
 * Subscribe to SSE events for a specific job
 */
export function useJobSSE(jobId: string | null, handler: SSEHandler) {
  const wrappedHandler = useCallback(
    (event: SSEEvent) => {
      handler(event);
    },
    [handler]
  );

  useEffect(() => {
    if (!jobId) return;

    const manager = getSSEManager();
    const unsubscribe = manager.subscribeToJob(jobId, wrappedHandler);

    return () => {
      unsubscribe();
    };
  }, [jobId, wrappedHandler]);
}

/**
 * Subscribe to all SSE events
 */
export function useGlobalSSE(handler: SSEHandler) {
  const wrappedHandler = useCallback(
    (event: SSEEvent) => {
      handler(event);
    },
    [handler]
  );

  useEffect(() => {
    const manager = getSSEManager();
    const unsubscribe = manager.subscribe(wrappedHandler);

    return () => {
      unsubscribe();
    };
  }, [wrappedHandler]);
}
