import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Phase, ConversationMessage } from '../../types';

interface ConversationViewProps {
  jobId: string;
  phase: Phase;
}

export function ConversationView({ jobId, phase }: ConversationViewProps) {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // TODO: Fetch conversation for this job/phase
    // For now, show placeholder
    setIsLoading(false);
    setMessages([]);
  }, [jobId, phase]);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [messages]);

  if (isLoading) {
    return <div className="conversation-loading">Loading conversation...</div>;
  }

  if (messages.length === 0) {
    return (
      <div className="conversation-empty">
        No conversation for this phase yet
      </div>
    );
  }

  return (
    <div className="conversation-view" ref={containerRef}>
      {messages.map((message, index) => (
        <div key={index} className={`conversation-message ${message.role}`}>
          <div className="message-header">
            <span className="message-role">{message.role}</span>
            <span className="message-time">
              {new Date(message.timestamp).toLocaleTimeString()}
            </span>
          </div>
          <div className="message-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
          {message.tool_calls && message.tool_calls.length > 0 && (
            <div className="message-tool-calls">
              {message.tool_calls.map((call, i) => (
                <div key={i} className="tool-call">
                  <span className="tool-name">{call.name}</span>
                  {call.result && (
                    <pre className="tool-result">{call.result}</pre>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
