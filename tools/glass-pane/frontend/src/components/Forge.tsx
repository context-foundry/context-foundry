import { useEffect, useState, useRef } from 'react';
import { Streamdown } from 'streamdown';
import { useChat } from '../contexts/ChatContext';

const MAX_MESSAGE_LENGTH = 10000;

export default function Forge() {
  const {
    currentSession,
    sessions,
    messages,
    streamingMessage,
    isStreaming,
    sendMessage,
    createSession,
    deleteSession,
    loadSessions,
    loadMessages,
    model,
    setModel,
    planMode,
    setPlanMode,
    bypassPermissions,
    setBypassPermissions,
    error,
    setError,
    cliStatus,
    checkCLIStatus,
  } = useChat();

  const [inputMessage, setInputMessage] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  const [showSessions, setShowSessions] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Check CLI status on mount and poll every 30 seconds
  useEffect(() => {
    checkCLIStatus();
    loadSessions();

    // Poll CLI status every 30 seconds
    const interval = setInterval(() => {
      checkCLIStatus();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  // Load messages when session changes
  useEffect(() => {
    if (currentSession) {
      loadMessages(currentSession.id);
    }
  }, [currentSession?.id]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingMessage]);

  const handleSend = async () => {
    if (!inputMessage.trim() || isStreaming) return;

    const message = inputMessage;
    setInputMessage('');
    setError(null);

    try {
      await sendMessage(message);
    } catch (err) {
      console.error('Failed to send message:', err);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewSession = async () => {
    try {
      await createSession();
      setShowSessions(false);
    } catch (err) {
      console.error('Failed to create session:', err);
    }
  };

  const handleSelectSession = async (sessionId: string) => {
    const session = sessions.find(s => s.id === sessionId);
    if (session) {
      await loadMessages(sessionId);
      setShowSessions(false);
    }
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Delete this session?')) {
      await deleteSession(sessionId);
    }
  };

  return (
    <div className="h-full flex flex-col bg-gray-900">
      {/* Header */}
      <div className="border-b border-gray-800 bg-gray-950 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🔥</span>
            <div>
              <h2 className="text-lg font-semibold text-gray-100">Forge</h2>
              <p className="text-xs text-gray-400">
                {currentSession ? currentSession.title || 'Untitled Session' : 'No session selected'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Sessions Button */}
            <button
              onClick={() => setShowSessions(!showSessions)}
              className="px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 rounded border border-gray-700 transition-colors"
              title="Sessions"
            >
              <span className="mr-1">💬</span>
              Sessions ({sessions.length})
            </button>

            {/* Settings Button */}
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="px-3 py-1.5 text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 rounded border border-gray-700 transition-colors"
              title="Settings"
            >
              <span className="mr-1">⚙️</span>
              Settings
            </button>

            {/* CLI Status */}
            {cliStatus && (
              <div className={`px-3 py-1.5 text-xs rounded ${
                cliStatus.available
                  ? 'bg-green-900/30 text-green-400 border border-green-800'
                  : 'bg-red-900/30 text-red-400 border border-red-800'
              }`}>
                {cliStatus.available ? '✓ CLI Ready' : '✗ CLI Not Found'}
              </div>
            )}
          </div>
        </div>

        {/* Settings Panel */}
        {showSettings && (
          <div className="mt-3 p-3 bg-gray-800 rounded border border-gray-700">
            <h3 className="text-sm font-semibold text-gray-300 mb-2">Chat Settings</h3>
            <div className="grid grid-cols-3 gap-4">
              {/* Model Selection */}
              <div>
                <label className="text-xs text-gray-400 block mb-1">Model</label>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value as 'sonnet' | 'opus' | 'haiku')}
                  className="w-full px-2 py-1 text-sm bg-gray-900 border border-gray-700 rounded text-gray-300"
                >
                  <option value="sonnet">Sonnet (Balanced)</option>
                  <option value="opus">Opus (Most Capable)</option>
                  <option value="haiku">Haiku (Fastest)</option>
                </select>
              </div>

              {/* Plan Mode Toggle */}
              <div>
                <label className="text-xs text-gray-400 block mb-1">Plan Mode</label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={planMode}
                    onChange={(e) => setPlanMode(e.target.checked)}
                    className="w-4 h-4"
                  />
                  <span className="text-sm text-gray-300">
                    {planMode ? 'Enabled' : 'Disabled'}
                  </span>
                </label>
              </div>

              {/* Bypass Permissions Toggle */}
              <div>
                <label className="text-xs text-gray-400 block mb-1">Bypass Permissions</label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={bypassPermissions}
                    onChange={(e) => setBypassPermissions(e.target.checked)}
                    className="w-4 h-4"
                  />
                  <span className="text-sm text-gray-300">
                    {bypassPermissions ? 'Enabled' : 'Disabled'}
                  </span>
                </label>
              </div>
            </div>
          </div>
        )}

        {/* Sessions Panel */}
        {showSessions && (
          <div className="mt-3 p-3 bg-gray-800 rounded border border-gray-700 max-h-64 overflow-y-auto">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold text-gray-300">Sessions</h3>
              <button
                onClick={handleNewSession}
                className="px-2 py-1 text-xs bg-cyan-600 hover:bg-cyan-500 text-white rounded transition-colors"
              >
                + New Session
              </button>
            </div>

            <div className="space-y-1">
              {sessions.length === 0 ? (
                <p className="text-xs text-gray-500 text-center py-4">No sessions yet</p>
              ) : (
                sessions.map((session) => (
                  <div
                    key={session.id}
                    onClick={() => handleSelectSession(session.id)}
                    className={`p-2 rounded cursor-pointer flex items-center justify-between group ${
                      currentSession?.id === session.id
                        ? 'bg-cyan-900/30 border border-cyan-700'
                        : 'bg-gray-900 hover:bg-gray-750 border border-gray-700'
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-gray-300 truncate">
                        {session.title || 'Untitled Session'}
                      </p>
                      <p className="text-xs text-gray-500">
                        {session.message_count} messages • {session.model}
                      </p>
                    </div>
                    <button
                      onClick={(e) => handleDeleteSession(session.id, e)}
                      className="ml-2 px-2 py-1 text-xs text-red-400 hover:text-red-300 opacity-0 group-hover:opacity-100 transition-opacity"
                      title="Delete session"
                    >
                      🗑️
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Error Display */}
        {error && (
          <div className="mt-3 p-2 bg-red-900/30 border border-red-800 rounded">
            <p className="text-sm text-red-400">{error}</p>
            <button
              onClick={() => setError(null)}
              className="mt-1 text-xs text-red-300 hover:underline"
            >
              Dismiss
            </button>
          </div>
        )}
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !streamingMessage ? (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <span className="text-6xl mb-4 block">🔥</span>
              <p className="text-lg font-semibold mb-2">Welcome to Forge</p>
              <p className="text-sm">Start chatting with Claude or create a new session</p>
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <div
                key={message.id}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-3xl rounded-lg px-4 py-3 ${
                    message.role === 'user'
                      ? 'bg-cyan-900/50 text-gray-100 border border-cyan-800'
                      : 'bg-gray-800 text-gray-100 border border-gray-700'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <span className="text-sm">
                      {message.role === 'user' ? '👤' : '🤖'}
                    </span>
                    <div className="flex-1">
                      <p className="text-xs text-gray-400 mb-1">
                        {message.role === 'user' ? 'You' : 'Claude'}
                      </p>
                      <div className="prose prose-invert prose-sm max-w-none">
                        <Streamdown>{message.content}</Streamdown>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}

            {/* Streaming Message */}
            {streamingMessage && (
              <div className="flex justify-start">
                <div className="max-w-3xl rounded-lg px-4 py-3 bg-gray-800 text-gray-100 border border-gray-700">
                  <div className="flex items-start gap-2">
                    <span className="text-sm">🤖</span>
                    <div className="flex-1">
                      <p className="text-xs text-gray-400 mb-1">Claude (streaming...)</p>
                      <div className="prose prose-invert prose-sm max-w-none">
                        <Streamdown>{streamingMessage}</Streamdown>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-800 bg-gray-950 p-4">
        <div className="flex gap-2">
          <div className="flex-1">
            <textarea
              value={inputMessage}
              onChange={(e) => {
                const value = e.target.value;
                if (value.length <= MAX_MESSAGE_LENGTH) {
                  setInputMessage(value);
                }
              }}
              onKeyDown={handleKeyDown}
              placeholder="Type your message... (Shift+Enter for new line, Enter to send)"
              disabled={isStreaming || !cliStatus?.available}
              className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded text-gray-100 placeholder-gray-500 resize-none focus:outline-none focus:border-cyan-600 disabled:opacity-50 disabled:cursor-not-allowed"
              rows={3}
            />
            {/* Character Counter */}
            <div className={`text-xs mt-1 text-right ${
              inputMessage.length > MAX_MESSAGE_LENGTH * 0.9
                ? 'text-yellow-500'
                : 'text-gray-500'
            }`}>
              {inputMessage.length} / {MAX_MESSAGE_LENGTH}
            </div>
          </div>
          <button
            onClick={handleSend}
            disabled={!inputMessage.trim() || isStreaming || !cliStatus?.available}
            className="px-6 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-cyan-600 self-start"
          >
            {isStreaming ? 'Sending...' : 'Send'}
          </button>
        </div>
        <p className="text-xs text-gray-500 mt-2">
          {model === 'opus' && '🚀 Using most capable model'}
          {model === 'sonnet' && '⚡ Using balanced model'}
          {model === 'haiku' && '💨 Using fastest model'}
          {planMode && ' • 📋 Plan mode enabled'}
          {bypassPermissions && ' • 🔓 Permissions bypassed'}
        </p>
      </div>
    </div>
  );
}
