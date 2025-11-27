import { useState, useEffect, useRef, useCallback } from 'react';

interface AgentEvent {
  event_type: string;
  session_id: string;
  timestamp: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_response?: string;
  prompt?: string;
  cwd?: string;
  received_at?: string;
}

interface Session {
  session_id: string;
  status: string;
  event_count: number;
  last_activity?: string;
  cwd?: string;
}

const TOOL_COLORS: Record<string, string> = {
  Bash: 'text-green-400',
  Read: 'text-blue-400',
  Write: 'text-yellow-400',
  Edit: 'text-orange-400',
  Glob: 'text-purple-400',
  Grep: 'text-pink-400',
  Task: 'text-cyan-400',
  WebFetch: 'text-indigo-400',
  WebSearch: 'text-violet-400',
  default: 'text-gray-400',
};

const EVENT_ICONS: Record<string, string> = {
  session_start: '🚀',
  session_end: '🏁',
  tool_start: '⚡',
  tool_complete: '✅',
  user_prompt: '💬',
  generic: '📌',
};

export default function AgentActivity() {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedSession, setSelectedSession] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const eventsEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Connect to SSE stream
  useEffect(() => {
    const connectSSE = () => {
      const url = selectedSession
        ? `/api/agent-events/stream?session_id=${selectedSession}`
        : '/api/agent-events/stream';

      const eventSource = new EventSource(url);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        setConnected(true);
      };

      eventSource.onmessage = (e) => {
        try {
          const message = JSON.parse(e.data);

          if (message.type === 'connected') {
            console.log('Connected to agent events stream');
          } else if (message.type === 'sessions') {
            setSessions(message.active || []);
          } else if (message.type === 'event') {
            setEvents((prev) => {
              const newEvents = [...prev, message.data];
              // Keep last 200 events
              return newEvents.slice(-200);
            });
          }
        } catch (err) {
          console.error('Failed to parse SSE message:', err);
        }
      };

      eventSource.onerror = () => {
        setConnected(false);
        eventSource.close();
        // Reconnect after 3 seconds
        setTimeout(connectSSE, 3000);
      };
    };

    connectSSE();

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [selectedSession]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && eventsEndRef.current) {
      eventsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [events, autoScroll]);

  // Fetch initial sessions
  useEffect(() => {
    fetch('/api/agent-events/sessions')
      .then((res) => res.json())
      .then((data) => {
        if (data.sessions) {
          setSessions(data.sessions);
        }
      })
      .catch((err) => console.error('Failed to fetch sessions:', err));
  }, []);

  // Format timestamp
  const formatTime = useCallback((timestamp: string) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return timestamp;
    }
  }, []);

  // Truncate long strings
  const truncate = (str: string, maxLen: number = 100) => {
    if (str.length <= maxLen) return str;
    return str.slice(0, maxLen) + '...';
  };

  // Get tool color
  const getToolColor = (toolName?: string) => {
    if (!toolName) return TOOL_COLORS.default;
    return TOOL_COLORS[toolName] || TOOL_COLORS.default;
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-gray-100">Agent Activity</h2>
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${
                connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
              }`}
            />
            <span className="text-xs text-gray-400">
              {connected ? 'Live' : 'Disconnected'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Session filter */}
          <select
            value={selectedSession || ''}
            onChange={(e) => setSelectedSession(e.target.value || null)}
            className="bg-gray-800 text-gray-300 text-sm rounded px-2 py-1 border border-gray-700 focus:border-cyan-500 focus:outline-none"
          >
            <option value="">All Sessions</option>
            {sessions.map((session) => (
              <option key={session.session_id} value={session.session_id}>
                {session.session_id.slice(0, 8)}... ({session.status})
              </option>
            ))}
          </select>

          {/* Auto-scroll toggle */}
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`px-2 py-1 text-xs rounded ${
              autoScroll
                ? 'bg-cyan-600 text-white'
                : 'bg-gray-700 text-gray-300'
            }`}
          >
            Auto-scroll {autoScroll ? 'ON' : 'OFF'}
          </button>

          {/* Clear */}
          <button
            onClick={() => setEvents([])}
            className="px-2 py-1 text-xs bg-gray-700 text-gray-300 rounded hover:bg-gray-600"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Events list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {events.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <div className="text-4xl mb-4">🤖</div>
            <p className="text-lg">Waiting for agent activity...</p>
            <p className="text-sm mt-2">
              Claude Code hooks will send events here when agents execute tools
            </p>
          </div>
        ) : (
          events.map((event, index) => (
            <div
              key={`${event.session_id}-${event.timestamp}-${index}`}
              className="bg-gray-800/50 rounded-lg p-3 border border-gray-700/50 hover:border-gray-600 transition-colors"
            >
              <div className="flex items-start gap-3">
                {/* Icon */}
                <div className="text-xl">
                  {EVENT_ICONS[event.event_type] || EVENT_ICONS.generic}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  {/* Header */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs text-gray-500">
                      {formatTime(event.timestamp)}
                    </span>
                    <span className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-300">
                      {event.event_type}
                    </span>
                    {event.tool_name && (
                      <span
                        className={`text-sm font-mono font-semibold ${getToolColor(
                          event.tool_name
                        )}`}
                      >
                        {event.tool_name}
                      </span>
                    )}
                    <span className="text-xs text-gray-600 font-mono">
                      {event.session_id.slice(0, 8)}
                    </span>
                  </div>

                  {/* Tool input */}
                  {event.tool_input && (
                    <div className="mt-2">
                      <pre className="text-xs text-gray-400 bg-gray-900 rounded p-2 overflow-x-auto">
                        {typeof event.tool_input === 'object'
                          ? truncate(JSON.stringify(event.tool_input, null, 2), 300)
                          : truncate(String(event.tool_input), 300)}
                      </pre>
                    </div>
                  )}

                  {/* Tool response (for completed tools) */}
                  {event.tool_response && event.event_type === 'tool_complete' && (
                    <div className="mt-2">
                      <div className="text-xs text-gray-500 mb-1">Response:</div>
                      <pre className="text-xs text-green-400/80 bg-gray-900 rounded p-2 overflow-x-auto max-h-32 overflow-y-auto">
                        {truncate(event.tool_response, 500)}
                      </pre>
                    </div>
                  )}

                  {/* User prompt */}
                  {event.prompt && (
                    <div className="mt-2 text-sm text-cyan-300 bg-cyan-900/20 rounded p-2">
                      {truncate(event.prompt, 200)}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={eventsEndRef} />
      </div>

      {/* Stats footer */}
      <div className="border-t border-gray-800 px-4 py-2 flex items-center justify-between text-xs text-gray-500">
        <span>{events.length} events</span>
        <span>{sessions.length} sessions tracked</span>
      </div>
    </div>
  );
}
