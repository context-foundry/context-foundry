/**
 * LogStream Component
 * Displays log entries with virtual scrolling
 */

import React, { useRef, useEffect } from 'react';

export default function LogStream({ logs, searchTerm = '' }) {
  const containerRef = useRef(null);
  const autoScrollRef = useRef(true);

  useEffect(() => {
    if (autoScrollRef.current && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);

  const highlightText = (text, term) => {
    if (!term) return text;

    const regex = new RegExp(`(${term})`, 'gi');
    const parts = text.split(regex);

    return parts.map((part, i) =>
      regex.test(part) ? <mark key={i} className="bg-yellow-300">{part}</mark> : part
    );
  };

  const getLevelColor = (level) => {
    switch (level) {
      case 'ERROR': return 'text-red-600';
      case 'WARNING': return 'text-yellow-600';
      default: return 'text-green-600';
    }
  };

  return (
    <div
      ref={containerRef}
      className="h-full overflow-y-auto bg-gray-900 text-gray-100 font-mono text-sm p-4"
      onScroll={(e) => {
        const { scrollTop, scrollHeight, clientHeight } = e.target;
        autoScrollRef.current = scrollTop + clientHeight >= scrollHeight - 50;
      }}
    >
      {logs.length === 0 ? (
        <div className="text-gray-500 text-center mt-8">
          Waiting for logs...
        </div>
      ) : (
        logs.map((log, index) => (
          <div key={index} className="mb-2 border-b border-gray-800 pb-2">
            <div className="flex gap-4">
              <span className="text-gray-500 w-24">
                {new Date(log.timestamp).toLocaleTimeString()}
              </span>
              <span className={`w-16 font-bold ${getLevelColor(log.level)}`}>
                {log.level}
              </span>
              <span className="text-blue-400">[{log.server}]</span>
              <span className="flex-1">
                {highlightText(log.message, searchTerm)}
              </span>
            </div>
            {log.structured_data && (
              <details className="mt-1 ml-44 text-xs text-gray-400">
                <summary className="cursor-pointer hover:text-gray-300">
                  View JSON data
                </summary>
                <pre className="mt-2 bg-gray-800 p-2 rounded overflow-x-auto">
                  {JSON.stringify(log.structured_data, null, 2)}
                </pre>
              </details>
            )}
            {log.tokens && (
              <div className="mt-1 ml-44 text-xs text-purple-400">
                Tokens: {log.tokens.input_tokens} in + {log.tokens.output_tokens} out = {log.tokens.total_tokens} total
              </div>
            )}
          </div>
        ))
      )}
    </div>
  );
}
