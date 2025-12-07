import { useState, useRef, useEffect } from 'react';
import { useSidekickStore } from '../../stores/sidekick';

export function SidekickInput() {
  const [input, setInput] = useState('');
  const { sendMessage, lastResponse, isLoading, openModal } = useSidekickStore();
  const inputRef = useRef<HTMLInputElement>(null);

  const handleKeyDown = async (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && input.trim()) {
      e.preventDefault();
      const message = input;
      setInput('');
      await sendMessage(message);
    }
  };

  // Truncate response for display
  const displayResponse = lastResponse
    ? lastResponse.length > 80
      ? lastResponse.slice(0, 80) + '...'
      : lastResponse
    : '';

  return (
    <div className="sidekick-container">
      {displayResponse && (
        <div
          className="sidekick-response"
          onClick={openModal}
          title="Click to see full conversation"
        >
          {displayResponse}
        </div>
      )}
      <div className="sidekick-input-wrapper">
        <input
          ref={inputRef}
          type="text"
          className="sidekick-input"
          placeholder="Say something to Context Foundry..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
        />
        {isLoading && <span className="sidekick-loading" />}
      </div>
    </div>
  );
}

export function SidekickModal() {
  const { messages, isOpen, isLoading, closeModal, sendMessage } = useSidekickStore();
  const [input, setInput] = useState('');
  const bodyRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [messages]);

  // Focus input when modal opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;
    const message = input;
    setInput('');
    await sendMessage(message);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const copyToClipboard = async (text: string, button: HTMLButtonElement) => {
    try {
      await navigator.clipboard.writeText(text);
      button.classList.add('copied');
      setTimeout(() => button.classList.remove('copied'), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="sidekick-modal-overlay" onClick={closeModal}>
      <div className="sidekick-modal" onClick={(e) => e.stopPropagation()}>
        <div className="sidekick-modal-header">
          <span className="sidekick-modal-title">Sidekick Conversation</span>
          <button className="sidekick-modal-close" onClick={closeModal}>
            &times;
          </button>
        </div>

        <div className="sidekick-modal-body" ref={bodyRef}>
          {messages.length === 0 ? (
            <div className="sidekick-empty">
              No conversation yet. Say something to Sidekick!
            </div>
          ) : (
            messages.map((msg, i) => (
              <div key={i} className={`sidekick-message ${msg.role}`}>
                <div className="sidekick-message-label">
                  {msg.role === 'user' ? 'You' : 'Sidekick'}
                </div>
                <div className="sidekick-message-content">{msg.content}</div>
                <button
                  className="sidekick-copy-btn"
                  onClick={(e) => copyToClipboard(msg.content, e.currentTarget)}
                  title="Copy to clipboard"
                >
                  Copy
                </button>
              </div>
            ))
          )}
          {isLoading && (
            <div className="sidekick-message assistant">
              <div className="sidekick-message-label">Sidekick</div>
              <div className="sidekick-message-content thinking">Thinking...</div>
            </div>
          )}
        </div>

        <div className="sidekick-modal-footer">
          <input
            ref={inputRef}
            type="text"
            className="sidekick-modal-input"
            placeholder="Type a message..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />
          <button
            className={`sidekick-send-btn ${isLoading ? 'loading' : ''}`}
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
          >
            <svg className="paper-airplane" viewBox="0 0 24 24" width="18" height="18">
              <path
                fill="currentColor"
                d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
