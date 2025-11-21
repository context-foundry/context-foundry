/**
 * Root application component.
 */

import TaskList from './components/TaskList';
import './styles/app.css';

function App() {
  return (
    <div className="app">
      <TaskList />
    </div>
  );
}

export default App;
