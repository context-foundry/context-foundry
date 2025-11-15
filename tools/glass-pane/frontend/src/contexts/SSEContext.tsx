import { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react';
import { SSEEvent } from '../types/events';

interface SSEContextValue {
  isConnected: boolean;
  subscribe: (jobId: string, handler: (event: SSEEvent) => void) => () => void;
  reconnect: () => void;
}

const SSEContext = createContext<SSEContextValue | undefined>(undefined);

export function SSEProvider({ children }: { children: ReactNode }) {
  const [isConnected, setIsConnected] = useState(false);
  const [eventSource, setEventSource] = useState<EventSource | null>(null);
  const [handlers, setHandlers] = useState<Map<string, (event: SSEEvent) => void>>(new Map());
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  const connect = useCallback((jobId: string) => {
    // Close existing connection
    if (eventSource) {
      eventSource.close();
    }

    const url = `/sse/jobs/${jobId}/updates`;
    const es = new EventSource(url);

    es.onopen = () => {
      setIsConnected(true);
      setReconnectAttempts(0);
      console.log('SSE connection established');
    };

    es.onerror = () => {
      setIsConnected(false);
      console.error('SSE connection error');
      es.close();

      // Exponential backoff: 1s, 2s, 4s, 8s (max)
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 8000);
      setReconnectAttempts(prev => prev + 1);

      setTimeout(() => {
        if (currentJobId) {
          connect(currentJobId);
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
          handlers.forEach(handler => handler(sseEvent));
        } catch (error) {
          console.error(`Error parsing ${eventType} event:`, error);
        }
      });
    });

    setEventSource(es);
    setCurrentJobId(jobId);
  }, [eventSource, handlers, reconnectAttempts, currentJobId]);

  const subscribe = useCallback((jobId: string, handler: (event: SSEEvent) => void) => {
    const handlerId = Math.random().toString(36).substring(7);
    setHandlers(prev => new Map(prev).set(handlerId, handler));

    // Connect if not already connected to this job
    if (currentJobId !== jobId) {
      connect(jobId);
    }

    // Return unsubscribe function
    return () => {
      setHandlers(prev => {
        const next = new Map(prev);
        next.delete(handlerId);
        return next;
      });
    };
  }, [currentJobId, connect]);

  const reconnect = useCallback(() => {
    if (currentJobId) {
      connect(currentJobId);
    }
  }, [currentJobId, connect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [eventSource]);

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
