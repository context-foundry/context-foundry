import ChatInterface from './components/ChatInterface'

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>Claude Chat</h1>
        <p className="subtitle">Powered by Claude Sonnet 4</p>
      </header>
      <ChatInterface />
    </div>
  )
}

export default App
