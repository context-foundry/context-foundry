import { useState, useCallback, useMemo, useEffect } from 'react';
import { LogEntry, LogLevel } from '../types/job';

export function useLogs(jobId: string | null) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [levelFilter, setLevelFilter] = useState<LogLevel | 'ALL'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [lastLogId, setLastLogId] = useState<number>(0);

  const fetchLogs = useCallback(async (sinceId?: number) => {
    if (!jobId) return;

    setIsLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({
        limit: '100',
      });

      if (sinceId !== undefined) {
        params.append('since_id', sinceId.toString());
      }

      const response = await fetch(`/api/jobs/${jobId}/logs?${params}`);

      if (!response.ok) {
        throw new Error(`Failed to fetch logs: ${response.statusText}`);
      }

      const data = await response.json() as { logs: LogEntry[] };

      if (sinceId !== undefined) {
        // Append new logs
        setLogs(prev => [...prev, ...data.logs]);
      } else {
        // Replace all logs
        setLogs(data.logs);
      }

      if (data.logs.length > 0) {
        const maxId = Math.max(...data.logs.map(log => log.id));
        setLastLogId(maxId);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      console.error('Error fetching logs:', err);
    } finally {
      setIsLoading(false);
    }
  }, [jobId]);

  const addLogs = useCallback((newLogs: LogEntry[]) => {
    setLogs(prev => {
      const combined = [...prev, ...newLogs];
      // Remove duplicates by id
      const unique = Array.from(new Map(combined.map(log => [log.id, log])).values());
      return unique.sort((a, b) => a.id - b.id);
    });

    if (newLogs.length > 0) {
      const maxId = Math.max(...newLogs.map(log => log.id));
      setLastLogId(prev => Math.max(prev, maxId));
    }
  }, []);

  const filteredLogs = useMemo(() => {
    let filtered = logs;

    // Apply level filter
    if (levelFilter !== 'ALL') {
      filtered = filtered.filter(log => log.level === levelFilter);
    }

    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(log =>
        log.message.toLowerCase().includes(query)
      );
    }

    return filtered;
  }, [logs, levelFilter, searchQuery]);

  const clearLogs = useCallback(() => {
    setLogs([]);
    setLastLogId(0);
  }, []);

  // Initial fetch when job changes
  useEffect(() => {
    if (jobId) {
      clearLogs();
      fetchLogs();
    }
  }, [jobId]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    logs: filteredLogs,
    allLogs: logs,
    isLoading,
    error,
    levelFilter,
    setLevelFilter,
    searchQuery,
    setSearchQuery,
    autoScroll,
    setAutoScroll,
    fetchLogs,
    addLogs,
    clearLogs,
    lastLogId,
  };
}
