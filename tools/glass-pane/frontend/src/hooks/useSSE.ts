import { useEffect, useCallback } from 'react';
import { useSSEContext } from '../contexts/SSEContext';
import { SSEEvent } from '../types/events';

export function useSSE(jobId: string | null, handler: (event: SSEEvent) => void) {
  const { subscribe, isConnected } = useSSEContext();

  const wrappedHandler = useCallback((event: SSEEvent) => {
    handler(event);
  }, [handler]);

  useEffect(() => {
    if (!jobId) return;

    const unsubscribe = subscribe(jobId, wrappedHandler);

    return () => {
      unsubscribe();
    };
  }, [jobId, subscribe, wrappedHandler]);

  return { isConnected };
}
