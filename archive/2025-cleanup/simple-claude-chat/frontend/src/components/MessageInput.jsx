import { useState } from 'react'

function MessageInput({ onSendMessage, disabled }) {
  const [input, setInput] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()

    if (input.trim() && !disabled) {
      onSendMessage(input.trim())
      setInput('')
    }
  }

  const handleKeyDown = (e) => {
    // Send message on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <form className="message-input" onSubmit={handleSubmit}>
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
        disabled={disabled}
        rows="3"
      />
      <button type="submit" disabled={disabled || !input.trim()}>
        {disabled ? 'Sending...' : 'Send'}
      </button>
    </form>
  )
}

export default MessageInput
