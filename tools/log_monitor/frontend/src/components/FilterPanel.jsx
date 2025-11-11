/**
 * FilterPanel Component
 * Controls for filtering logs
 */

import React from 'react';

export default function FilterPanel({ filters, onFilterChange }) {
  return (
    <div className="bg-gray-800 p-4 rounded-lg mb-4">
      <h3 className="text-white font-bold mb-3">Filters</h3>

      <div className="grid grid-cols-3 gap-4">
        {/* Log Level Filter */}
        <div>
          <label className="block text-gray-300 text-sm mb-2">Log Level</label>
          <div className="space-y-1">
            {['INFO', 'WARNING', 'ERROR'].map(level => (
              <label key={level} className="flex items-center text-gray-300">
                <input
                  type="checkbox"
                  checked={filters.levels.includes(level)}
                  onChange={(e) => {
                    const newLevels = e.target.checked
                      ? [...filters.levels, level]
                      : filters.levels.filter(l => l !== level);
                    onFilterChange({ ...filters, levels: newLevels });
                  }}
                  className="mr-2"
                />
                {level}
              </label>
            ))}
          </div>
        </div>

        {/* Search */}
        <div>
          <label className="block text-gray-300 text-sm mb-2">Search</label>
          <input
            type="text"
            placeholder="Search logs..."
            value={filters.searchTerm}
            onChange={(e) => onFilterChange({ ...filters, searchTerm: e.target.value })}
            className="w-full px-3 py-2 bg-gray-700 text-white rounded"
          />
        </div>

        {/* Server Filter */}
        <div>
          <label className="block text-gray-300 text-sm mb-2">Server</label>
          <select
            value={filters.server}
            onChange={(e) => onFilterChange({ ...filters, server: e.target.value })}
            className="w-full px-3 py-2 bg-gray-700 text-white rounded"
          >
            <option value="all">All Servers</option>
            <option value="context-foundry">Context Foundry</option>
            <option value="claude-desktop">Claude Desktop</option>
          </select>
        </div>
      </div>
    </div>
  );
}
