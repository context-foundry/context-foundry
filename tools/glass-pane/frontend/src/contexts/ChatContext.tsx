import { createContext, useContext, useState, useCallback, ReactNode, useRef, useEffect } from 'react';
import { ChatMessage, ChatSession, SendMessageRequest, CLIStatus } from '../types/chat';

interface ChatContextValue {
  // Session management
  currentSession: ChatSession | null;
  setCurrentSession: (session: ChatSession | null) => void;
  sessions: ChatSession[];
  loadSessions: () => Promise<void>;
  createSession: () => Promise<ChatSession>;
  updateSession: (sessionId: string, updates: { working_directory?: string }) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;

  // Message management
  messages: ChatMessage[];
  setMessages: (messages: ChatMessage[]) => void;
  loadMessages: (sessionId: string) => Promise<void>;
  clearMessages: () => void;

  // Chat functionality
  sendMessage: (content: string) => Promise<void>;
  isStreaming: boolean;
  streamingMessage: string;

  // Settings
  model: 'sonnet' | 'opus' | 'haiku';
  setModel: (model: 'sonnet' | 'opus' | 'haiku') => void;
  planMode: boolean;
  setPlanMode: (enabled: boolean) => void;
  bypassPermissions: boolean;
  setBypassPermissions: (enabled: boolean) => void;
  workingDirectory: string;
  setWorkingDirectory: (dir: string) => void;

  // CLI status
  cliStatus: CLIStatus | null;
  checkCLIStatus: () => Promise<void>;

  // Error handling
  error: string | null;
  setError: (error: string | null) => void;
}

const ChatContext = createContext<ChatContextValue | undefined>(undefined);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [currentSession, setCurrentSession] = useState<ChatSession | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingMessage, setStreamingMessage] = useState('');
  const [model, setModel] = useState<'sonnet' | 'opus' | 'haiku'>('sonnet');
  const [planMode, setPlanMode] = useState(false);
  const [bypassPermissions, setBypassPermissions] = useState(false);
  const [workingDirectory, setWorkingDirectory] = useState('');
  const [cliStatus, setCLIStatus] = useState<CLIStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);

  // Clean up EventSource on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  // Sync workingDirectory state when currentSession changes
  useEffect(() => {
    if (currentSession?.working_directory) {
      setWorkingDirectory(currentSession.working_directory);
    }
  }, [currentSession?.id]);

  // Load sessions list
  const loadSessions = useCallback(async () => {
    try {
      const response = await fetch('/api/chat/sessions');
      if (!response.ok) {
        throw new Error(`Failed to load sessions: ${response.statusText}`);
      }
      const data = await response.json();
      setSessions(data.sessions || []);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load sessions';
      setError(errorMessage);
      console.error('Error loading sessions:', err);
    }
  }, []);

  // Create new session
  const createSession = useCallback(async (): Promise<ChatSession> => {
    try {
      const response = await fetch('/api/chat/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model,
          plan_mode: planMode,
          bypass_permissions: bypassPermissions,
          title: `Chat - ${new Date().toLocaleString()}`,
          working_directory: workingDirectory || undefined
        })
      });

      if (!response.ok) {
        throw new Error(`Failed to create session: ${response.statusText}`);
      }

      const session = await response.json();
      setCurrentSession(session);
      setSessions(prev => [session, ...prev]);
      setMessages([]);
      return session;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create session';
      setError(errorMessage);
      console.error('Error creating session:', err);
      throw err;
    }
  }, [model, planMode, bypassPermissions, workingDirectory]);

  // Update session
  const updateSession = useCallback(async (sessionId: string, updates: { working_directory?: string }) => {
    try {
      const response = await fetch(`/api/chat/sessions/${sessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });

      if (!response.ok) {
        throw new Error(`Failed to update session: ${response.statusText}`);
      }

      const updatedSession = await response.json();

      // Update in sessions list
      setSessions(prev => prev.map(s => s.id === sessionId ? updatedSession : s));

      // Update current session if it's the one being updated
      if (currentSession?.id === sessionId) {
        setCurrentSession(updatedSession);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to update session';
      setError(errorMessage);
      console.error('Error updating session:', err);
      throw err;
    }
  }, [currentSession]);

  // Delete session
  const deleteSession = useCallback(async (sessionId: string) => {
    try {
      const response = await fetch(`/api/chat/sessions/${sessionId}`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        throw new Error(`Failed to delete session: ${response.statusText}`);
      }

      setSessions(prev => prev.filter(s => s.id !== sessionId));
      if (currentSession?.id === sessionId) {
        setCurrentSession(null);
        setMessages([]);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to delete session';
      setError(errorMessage);
      console.error('Error deleting session:', err);
    }
  }, [currentSession]);

  // Load messages for a session
  const loadMessages = useCallback(async (sessionId: string) => {
    try {
      const response = await fetch(`/api/chat/sessions/${sessionId}`);
      if (!response.ok) {
        throw new Error(`Failed to load messages: ${response.statusText}`);
      }
      const data = await response.json();
      setCurrentSession(data.session);
      setMessages(data.messages || []);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load messages';
      setError(errorMessage);
      console.error('Error loading messages:', err);
    }
  }, []);

  // Clear messages (for UI)
  const clearMessages = useCallback(() => {
    setMessages([]);
    setStreamingMessage('');
  }, []);

  // Send message and stream response
  const sendMessage = useCallback(async (content: string) => {
    try {
      setError(null);
      setIsStreaming(true);
      setStreamingMessage('');

      // Create user message immediately
      const userMessage: ChatMessage = {
        id: Date.now(), // Temporary ID
        session_id: currentSession?.id || '',
        role: 'user',
        content,
        timestamp: new Date().toISOString()
      };

      setMessages(prev => [...prev, userMessage]);

      // Close existing EventSource if any
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      // Prepare request
      const request: SendMessageRequest = {
        session_id: currentSession?.id,
        message: content,
        model,
        plan_mode: planMode,
        bypass_permissions: bypassPermissions,
        working_directory: workingDirectory || undefined
      };

      // Use fetch with SSE
      const response = await fetch('/api/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
      });

      if (!response.ok) {
        throw new Error(`Failed to send message: ${response.statusText}`);
      }

      // Read SSE stream
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let accumulatedResponse = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));

                if (data.type === 'delta') {
                  accumulatedResponse += data.text || '';
                  setStreamingMessage(accumulatedResponse);
                } else if (data.type === 'complete') {
                  // Update session ID if new session was created
                  if (data.session_id && !currentSession) {
                    // Load the full session data including messages
                    const response = await fetch(`/api/chat/sessions/${data.session_id}`);
                    if (response.ok) {
                      const sessionData = await response.json();
                      setCurrentSession(sessionData.session);
                      setMessages(sessionData.messages);
                      // Add to sessions list if not already present
                      setSessions(prev => {
                        const exists = prev.some(s => s.id === sessionData.session.id);
                        return exists ? prev : [sessionData.session, ...prev];
                      });
                    }
                  } else {
                    // Add assistant message
                    const assistantMessage: ChatMessage = {
                      id: Date.now() + 1,
                      session_id: data.session_id || currentSession?.id || '',
                      role: 'assistant',
                      content: data.text || accumulatedResponse,
                      timestamp: new Date().toISOString()
                    };
                    setMessages(prev => [...prev, assistantMessage]);
                  }
                  setStreamingMessage('');
                } else if (data.type === 'error') {
                  setError(data.message || 'An error occurred');
                }
              } catch (e) {
                console.warn('Failed to parse SSE event:', line);
              }
            }
          }
        }
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to send message';
      setError(errorMessage);
      console.error('Error sending message:', err);
    } finally {
      setIsStreaming(false);
      setStreamingMessage('');
    }
  }, [currentSession, model, planMode, bypassPermissions, workingDirectory, loadMessages]);

  // Check Claude CLI status
  const checkCLIStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/chat/cli-status');
      if (!response.ok) {
        throw new Error(`Failed to check CLI status: ${response.statusText}`);
      }
      const status = await response.json();
      setCLIStatus(status);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to check CLI status';
      setError(errorMessage);
      console.error('Error checking CLI status:', err);
    }
  }, []);

  return (
    <ChatContext.Provider
      value={{
        currentSession,
        setCurrentSession,
        sessions,
        loadSessions,
        createSession,
        updateSession,
        deleteSession,
        messages,
        setMessages,
        loadMessages,
        clearMessages,
        sendMessage,
        isStreaming,
        streamingMessage,
        model,
        setModel,
        planMode,
        setPlanMode,
        bypassPermissions,
        setBypassPermissions,
        workingDirectory,
        setWorkingDirectory,
        cliStatus,
        checkCLIStatus,
        error,
        setError,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const context = useContext(ChatContext);
  if (context === undefined) {
    throw new Error('useChat must be used within a ChatProvider');
  }
  return context;
}
