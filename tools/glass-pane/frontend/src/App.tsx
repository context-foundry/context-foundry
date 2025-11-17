import { JobProvider } from './contexts/JobContext';
import { SSEProvider } from './contexts/SSEContext';
import { ThemeProvider } from './contexts/ThemeContext';
import { ChatProvider } from './contexts/ChatContext';
import Dashboard from './components/Dashboard';

function App() {
  return (
    <ThemeProvider>
      <SSEProvider>
        <JobProvider>
          <ChatProvider>
            <Dashboard />
          </ChatProvider>
        </JobProvider>
      </SSEProvider>
    </ThemeProvider>
  );
}

export default App;
