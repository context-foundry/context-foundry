import { JobProvider } from './contexts/JobContext';
import { SSEProvider } from './contexts/SSEContext';
import { ThemeProvider } from './contexts/ThemeContext';
import Dashboard from './components/Dashboard';

function App() {
  return (
    <ThemeProvider>
      <SSEProvider>
        <JobProvider>
          <Dashboard />
        </JobProvider>
      </SSEProvider>
    </ThemeProvider>
  );
}

export default App;
