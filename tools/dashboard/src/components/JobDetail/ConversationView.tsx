import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Phase, ConversationMessage } from '../../types';
import * as api from '../../api/client';
import { CollapsibleSection } from '../common/CollapsibleSection';
import { SearchBox } from '../common/SearchBox';

interface ConversationViewProps {
  jobId: string;
  phase: Phase;
}

export function ConversationView({ jobId, phase }: ConversationViewProps) {
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentMatchIndex, setCurrentMatchIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const matchRefs = useRef<(HTMLElement | null)[]>([]);

  useEffect(() => {
    async function fetchConversation() {
      setIsLoading(true);
      setError(null);
      try {
        const conversation = await api.getJobConversation(jobId, phase);
        // Transform API response to ConversationMessage format
        const msgs: ConversationMessage[] = conversation.map((msg) => ({
          role: msg.role as 'user' | 'assistant' | 'system',
          content: msg.content,
          timestamp: new Date().toISOString(), // API may not provide timestamp
        }));
        setMessages(msgs);
      } catch (err) {
        console.error('Failed to fetch conversation:', err);
        setError('Failed to load conversation');
        setMessages([]);
      } finally {
        setIsLoading(false);
      }
    }

    fetchConversation();
  }, [jobId, phase]);

  // Calculate matches
  const matches = useMemo(() => {
    if (!searchQuery.trim()) return [];

    const results: { messageIndex: number; matchIndex: number }[] = [];
    const regex = new RegExp(escapeRegExp(searchQuery), 'gi');

    messages.forEach((message, msgIdx) => {
      while (regex.exec(message.content) !== null) {
        results.push({ messageIndex: msgIdx, matchIndex: results.length });
      }
    });

    return results;
  }, [messages, searchQuery]);

  // Reset current match when query changes
  useEffect(() => {
    setCurrentMatchIndex(matches.length > 0 ? 1 : 0);
  }, [matches.length, searchQuery]);

  // Scroll to current match
  useEffect(() => {
    if (currentMatchIndex > 0 && matchRefs.current[currentMatchIndex - 1]) {
      matchRefs.current[currentMatchIndex - 1]?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [currentMatchIndex]);

  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query);
  }, []);

  const handleNavigate = useCallback((direction: 'prev' | 'next') => {
    if (matches.length === 0) return;

    setCurrentMatchIndex((prev) => {
      if (direction === 'next') {
        return prev >= matches.length ? 1 : prev + 1;
      } else {
        return prev <= 1 ? matches.length : prev - 1;
      }
    });
  }, [matches.length]);

  // Render message content with search highlighting
  const renderContent = useCallback(
    (content: string, messageIndex: number) => {
      if (!searchQuery.trim()) {
        return (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
        );
      }

      // For search mode, we'll highlight within the raw text
      // This is a simplified approach - full markdown + highlighting would need more work
      const parts = splitWithHighlight(content, searchQuery);
      let globalMatchIdx = 0;

      // Count matches before this message
      for (let i = 0; i < messageIndex; i++) {
        const regex = new RegExp(escapeRegExp(searchQuery), 'gi');
        while (regex.exec(messages[i].content) !== null) {
          globalMatchIdx++;
        }
      }

      return (
        <div className="message-content-searchable">
          {parts.map((part, i) => {
            if (part.isMatch) {
              globalMatchIdx++;
              const isCurrentMatch = globalMatchIdx === currentMatchIndex;
              return (
                <mark
                  key={i}
                  ref={(el) => {
                    if (el) matchRefs.current[globalMatchIdx - 1] = el;
                  }}
                  className={`search-highlight ${isCurrentMatch ? 'current' : ''}`}
                >
                  {part.text}
                </mark>
              );
            }
            return <span key={i}>{part.text}</span>;
          })}
        </div>
      );
    },
    [searchQuery, currentMatchIndex, messages]
  );

  const searchHeader = (
    <SearchBox
      placeholder="Search conversation..."
      onSearch={handleSearch}
      matchCount={matches.length}
      currentMatch={currentMatchIndex}
      onNavigate={handleNavigate}
    />
  );

  if (isLoading) {
    return (
      <CollapsibleSection title="Agent Conversation" headerContent={null}>
        <div className="conversation-loading">Loading conversation...</div>
      </CollapsibleSection>
    );
  }

  if (error) {
    return (
      <CollapsibleSection title="Agent Conversation" headerContent={null}>
        <div className="conversation-empty">{error}</div>
      </CollapsibleSection>
    );
  }

  if (messages.length === 0) {
    return (
      <CollapsibleSection title="Agent Conversation" headerContent={null}>
        <div className="conversation-empty">
          No conversation for this phase yet
        </div>
      </CollapsibleSection>
    );
  }

  return (
    <CollapsibleSection title="Agent Conversation" headerContent={searchHeader}>
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
              {renderContent(message.content, index)}
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
    </CollapsibleSection>
  );
}

// Helper functions
function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function splitWithHighlight(text: string, query: string): { text: string; isMatch: boolean }[] {
  if (!query.trim()) return [{ text, isMatch: false }];

  const regex = new RegExp(`(${escapeRegExp(query)})`, 'gi');
  const parts = text.split(regex);

  return parts.filter(Boolean).map((part) => ({
    text: part,
    isMatch: regex.test(part) || part.toLowerCase() === query.toLowerCase(),
  }));
}
