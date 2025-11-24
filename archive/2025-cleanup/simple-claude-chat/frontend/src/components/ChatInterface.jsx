import { useState } from 'react'
import MessageList from './MessageList'
import MessageInput from './MessageInput'

function ChatInterface() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const sendMessage = async (userMessage) => {
    // Clear any previous errors
    setError(null)

    // Add user message to the conversation
    const newMessages = [...messages, { role: 'user', content: userMessage }]
    setMessages(newMessages)
    setIsLoading(true)

    try {
      const response = await fetch('http://localhost:3001/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ messages: newMessages }),
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Failed to get response from server')
      }

      const data = await response.json()

      // Add assistant's response to the conversation
      setMessages([...newMessages, data])
    } catch (err) {
      console.error('Error sending message:', err)
      setError(err.message || 'Failed to send message. Please check if the backend is running.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="chat-interface">
      <MessageList messages={messages} isLoading={isLoading} />
      {error && (
        <div className="error-message">
          <strong>Error:</strong> {error}
        </div>
      )}
      <MessageInput onSendMessage={sendMessage} disabled={isLoading} />
    </div>
  )
}

export default ChatInterface
