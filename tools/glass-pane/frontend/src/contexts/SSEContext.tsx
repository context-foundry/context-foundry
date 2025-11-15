import { createContext, useContext, useState, useCallback, ReactNode, useEffect, useRef } from 'react';
import { SSEEvent } from '../types/events';

interface SSEContextValue {
  isConnected: boolean;
  subscribe: (jobId: string, handler: (event: SSEEvent) => void) => () => void;
  reconnect: () => void;
}

const SSEContext = createContext<SSEContextValue | undefined>(undefined);

export function SSEProvider({ children }: { children: ReactNode }) {
  const [isConnected, setIsConnected] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);
  const currentJobIdRef = useRef<string | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const handlersRef = useRef<Map<string, (event: SSEEvent) => void>>(new Map());

  const connect = useCallback((jobId: string) => {
    console.log(`[SSE] connect() called for job ${jobId}, existing eventSource:`, !!eventSourceRef.current);

    // Close existing connection
    if (eventSourceRef.current) {
      console.log('[SSE] Closing existing EventSource');
      eventSourceRef.current.close();
    }

    const url = `/sse/jobs/${jobId}/updates`;
    console.log(`[SSE] Creating new EventSource for ${url}`);
    const es = new EventSource(url);

    es.onopen = () => {
      console.log('[SSE] EventSource.onopen - connection established');
      setIsConnected(true);
      reconnectAttemptsRef.current = 0;
    };

    es.onerror = (error) => {
      console.error('[SSE] EventSource.onerror - connection error:', error);
      setIsConnected(false);
      es.close();

      // Exponential backoff: 1s, 2s, 4s, 8s (max)
      const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 8000);
      console.log(`[SSE] Scheduling reconnect in ${delay}ms (attempt ${reconnectAttemptsRef.current})`);
      reconnectAttemptsRef.current += 1;

      setTimeout(() => {
        console.log('[SSE] Reconnect timeout fired, currentJobId:', currentJobIdRef.current);
        if (currentJobIdRef.current) {
          connect(currentJobIdRef.current);
        }
      }, delay);
    };

    // Listen for all event types
    const eventTypes = ['phase_update', 'file_created', 'log_batch', 'metrics_update', 'job_status_change', 'heartbeat'];

    eventTypes.forEach(eventType => {
      es.addEventListener(eventType, (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          const sseEvent: SSEEvent = { type: eventType as any, data };

          // Notify all handlers
          handlersRef.current.forEach(handler => handler(sseEvent));
        } catch (error) {
          console.error(`Error parsing ${eventType} event:`, error);
        }
      });
    });

    eventSourceRef.current = es;
    currentJobIdRef.current = jobId;
  }, []);

  const subscribe = useCallback((jobId: string, handler: (event: SSEEvent) => void) => {
    const handlerId = Math.random().toString(36).substring(7);
    console.log(`[SSE] subscribe() called for job ${jobId}, handler ${handlerId}, currentJobId: ${currentJobIdRef.current}`);
    handlersRef.current.set(handlerId, handler);

    // Connect if not already connected to this job
    if (currentJobIdRef.current !== jobId) {
      console.log(`[SSE] Job ID changed (${currentJobIdRef.current} -> ${jobId}), calling connect()`);
      connect(jobId);
    } else {
      console.log('[SSE] Already connected to this job, not reconnecting');
    }

    // Return unsubscribe function
    return () => {
      console.log(`[SSE] unsubscribe() called for handler ${handlerId}`);
      handlersRef.current.delete(handlerId);

      // If no subscribers remain, close the SSE connection
      if (handlersRef.current.size === 0 && eventSourceRef.current) {
        console.log('[SSE] No subscribers remain, closing EventSource');
        eventSourceRef.current.close();
        eventSourceRef.current = null;
        currentJobIdRef.current = null;
        setIsConnected(false);
      }
    };
  }, [connect]);

  const reconnect = useCallback(() => {
    if (currentJobIdRef.current) {
      connect(currentJobIdRef.current);
    }
  }, [connect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return (
    <SSEContext.Provider value={{ isConnected, subscribe, reconnect }}>
      {children}
    </SSEContext.Provider>
  );
}

export function useSSEContext() {
  const context = useContext(SSEContext);
  if (context === undefined) {
    throw new Error('useSSEContext must be used within an SSEProvider');
  }
  return context;
}
