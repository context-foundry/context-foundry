import React, { useEffect, useRef } from 'react';
import { FixedSizeList as List } from 'react-window';
import { useLogs } from '../hooks/useLogs';
import { LogLevel } from '../types/job';
import { formatTimestamp } from '../utils/formatters';

interface LogFeedProps {
  jobId: string | null;
}

const LOG_LEVELS: (LogLevel | 'ALL')[] = ['ALL', LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR];

export default function LogFeed({ jobId }: LogFeedProps) {
  const {
    logs,
    isLoading,
    error,
    levelFilter,
    setLevelFilter,
    searchQuery,
    setSearchQuery,
    autoScroll,
    setAutoScroll,
  } = useLogs(jobId);

  const listRef = useRef<List>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && listRef.current && logs.length > 0) {
      listRef.current.scrollToItem(logs.length - 1, 'end');
    }
  }, [logs.length, autoScroll]);

  const getLevelColor = (level: LogLevel): string => {
    switch (level) {
      case LogLevel.DEBUG:
        return 'text-gray-400';
      case LogLevel.INFO:
        return 'text-cyan-400';
      case LogLevel.WARNING:
        return 'text-yellow-400';
      case LogLevel.ERROR:
        return 'text-red-400';
      default:
        return 'text-gray-300';
    }
  };

  const getLevelBadge = (level: LogLevel): string => {
    switch (level) {
      case LogLevel.DEBUG:
        return 'bg-gray-500/20';
      case LogLevel.INFO:
        return 'bg-cyan-500/20';
      case LogLevel.WARNING:
        return 'bg-yellow-500/20';
      case LogLevel.ERROR:
        return 'bg-red-500/20';
      default:
        return 'bg-gray-500/20';
    }
  };

  const Row = ({ index, style }: { index: number; style: React.CSSProperties }) => {
    const log = logs[index];

    return (
      <div style={style} className="px-4 py-1 hover:bg-gray-800/50 transition-colors">
        <div className="flex items-start gap-3 text-sm font-mono">
          {/* Timestamp */}
          <span className="text-gray-500 text-xs whitespace-nowrap">
            {formatTimestamp(log.timestamp)}
          </span>

          {/* Level Badge */}
          <span
            className={`px-2 py-0.5 rounded text-xs font-semibold ${getLevelBadge(log.level)} ${getLevelColor(log.level)} whitespace-nowrap`}
          >
            {log.level}
          </span>

          {/* Message */}
          <span className="text-gray-300 flex-1 break-words">{log.message}</span>
        </div>
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-gray-800 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-100">Logs</h2>

          {/* Auto-scroll Toggle */}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="w-4 h-4 rounded bg-gray-800 border-gray-700 text-cyan-500 focus:ring-2 focus:ring-cyan-500"
            />
            <span className="text-sm text-gray-400">Auto-scroll</span>
          </label>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3">
          {/* Level Filter */}
          <div className="flex gap-2 flex-wrap">
            {LOG_LEVELS.map(level => (
              <button
                key={level}
                onClick={() => setLevelFilter(level)}
                className={`px-3 py-1 text-xs rounded-lg transition-colors ${
                  levelFilter === level
                    ? 'bg-cyan-500 text-white'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {level}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative flex-1">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search logs..."
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-1 pl-8 text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500"
            />
            <svg
              className="w-4 h-4 absolute left-2 top-1/2 transform -translate-y-1/2 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        </div>
      </div>

      {/* Content */}
      <div ref={containerRef} className="flex-1 overflow-hidden">
        {!jobId && (
          <div className="flex items-center justify-center h-full text-gray-500">
            Select a job to view logs
          </div>
        )}

        {isLoading && (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500" />
          </div>
        )}

        {error && (
          <div className="flex items-center justify-center h-full">
            <div className="text-red-400 text-sm">{error}</div>
          </div>
        )}

        {jobId && logs.length > 0 && !isLoading && !error && (
          <List
            ref={listRef}
            height={containerRef.current?.clientHeight || 400}
            itemCount={logs.length}
            itemSize={40}
            width="100%"
          >
            {Row}
          </List>
        )}

        {jobId && logs.length === 0 && !isLoading && !error && (
          <div className="flex items-center justify-center h-full text-gray-500">
            {searchQuery || levelFilter !== 'ALL' ? 'No logs match your filters' : 'No logs yet'}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-2 border-t border-gray-800 bg-gray-800/50">
        <div className="text-xs text-gray-400">
          {logs.length} log{logs.length !== 1 ? 's' : ''} {searchQuery || levelFilter !== 'ALL' ? '(filtered)' : ''}
        </div>
      </div>
    </div>
  );
}
