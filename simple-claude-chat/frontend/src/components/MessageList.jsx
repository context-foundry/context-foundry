import { useEffect, useRef } from 'react'

function MessageList({ messages, isLoading }) {
  const messagesEndRef = useRef(null)

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, isLoading])

  return (
    <div className="message-list">
      {messages.length === 0 && (
        <div className="welcome-message">
          <h2>Welcome to Claude Chat!</h2>
          <p>Start a conversation by typing a message below.</p>
        </div>
      )}

      {messages.map((message, index) => (
        <div
          key={index}
          className={`message ${message.role === 'user' ? 'message-user' : 'message-assistant'}`}
        >
          <div className="message-role">
            {message.role === 'user' ? '👤 You' : '🤖 Claude'}
          </div>
          <div className="message-content">{message.content}</div>
        </div>
      ))}

      {isLoading && (
        <div className="message message-assistant">
          <div className="message-role">🤖 Claude</div>
          <div className="message-content loading">
            <span className="loading-dot">.</span>
            <span className="loading-dot">.</span>
            <span className="loading-dot">.</span>
          </div>
        </div>
      )}

      <div ref={messagesEndRef} />
    </div>
  )
}

export default MessageList
