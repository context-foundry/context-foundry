/**
 * ServerTabs Component
 * Tabs for switching between different servers
 */

import React from 'react';

export default function ServerTabs({ activeChannel, onChannelChange, servers = [] }) {
  const defaultServers = [
    { name: 'all', label: 'All Servers' },
    { name: 'context-foundry', label: 'Context Foundry' },
    { name: 'claude-desktop', label: 'Claude Desktop' }
  ];

  return (
    <div className="flex gap-2 border-b border-gray-700 mb-4">
      {defaultServers.map(server => (
        <button
          key={server.name}
          onClick={() => onChannelChange(server.name)}
          className={`px-4 py-2 font-medium transition-colors ${
            activeChannel === server.name
              ? 'bg-blue-600 text-white border-b-2 border-blue-400'
              : 'text-gray-400 hover:text-gray-200'
          }`}
        >
          {server.label}
        </button>
      ))}
    </div>
  );
}
