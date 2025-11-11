/**
 * Main App Component
 * MCP Log Monitor Dashboard
 */

import React, { useState, useMemo } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import LogStream from './components/LogStream';
import FilterPanel from './components/FilterPanel';
import ServerTabs from './components/ServerTabs';

function App() {
  const [activeChannel, setActiveChannel] = useState('all');
  const [filters, setFilters] = useState({
    levels: ['INFO', 'WARNING', 'ERROR'],
    searchTerm: '',
    server: 'all'
  });

  const { isConnected, logs, clearLogs } = useWebSocket(activeChannel);

  // Apply filters to logs
  const filteredLogs = useMemo(() => {
    return logs.filter(log => {
      // Filter by level
      if (!filters.levels.includes(log.level)) {
        return false;
      }

      // Filter by server
      if (filters.server !== 'all' && log.server !== filters.server) {
        return false;
      }

      // Filter by search term
      if (filters.searchTerm && !log.message.toLowerCase().includes(filters.searchTerm.toLowerCase())) {
        return false;
      }

      return true;
    });
  }, [logs, filters]);

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="bg-gray-900 border-b border-gray-800 p-4">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold">MCP Log Monitor</h1>
            <p className="text-gray-400 text-sm">Real-time Model Context Protocol log streaming</p>
          </div>
          <div className="flex items-center gap-4">
            <div className={`flex items-center gap-2 ${isConnected ? 'text-green-500' : 'text-red-500'}`}>
              <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
              {isConnected ? 'Connected' : 'Disconnected'}
            </div>
            <button
              onClick={clearLogs}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded transition"
            >
              Clear Logs
            </button>
            <div className="text-gray-400 text-sm">
              {filteredLogs.length} / {logs.length} logs
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto p-4">
        <ServerTabs
          activeChannel={activeChannel}
          onChannelChange={setActiveChannel}
        />

        <FilterPanel
          filters={filters}
          onFilterChange={setFilters}
        />

        <div className="bg-gray-900 rounded-lg overflow-hidden h-[600px]">
          <LogStream
            logs={filteredLogs}
            searchTerm={filters.searchTerm}
          />
        </div>
      </div>
    </div>
  );
}

export default App;
