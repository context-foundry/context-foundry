'use client';

import React, { useState } from 'react';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { MatchStatus } from '@/types/match';

export interface MatchFiltersProps {
  onFilterChange: (filters: {
    status?: MatchStatus;
    search?: string;
    date?: string;
  }) => void;
}

export function MatchFilters({ onFilterChange }: MatchFiltersProps) {
  const [status, setStatus] = useState<MatchStatus | ''>('');
  const [search, setSearch] = useState('');
  const [date, setDate] = useState('');

  const handleApply = () => {
    onFilterChange({
      status: status || undefined,
      search: search || undefined,
      date: date || undefined,
    });
  };

  const handleReset = () => {
    setStatus('');
    setSearch('');
    setDate('');
    onFilterChange({});
  };

  return (
    <div className="bg-white p-4 rounded-lg border border-gray-200 space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div>
          <label htmlFor="status" className="block text-sm font-medium text-gray-700 mb-1">
            Status
          </label>
          <select
            id="status"
            value={status}
            onChange={(e) => setStatus(e.target.value as MatchStatus | '')}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[44px]"
          >
            <option value="">All</option>
            <option value="scheduled">Scheduled</option>
            <option value="in_progress">Live</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        <Input
          type="text"
          label="Search Players"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Player name..."
        />

        <Input
          type="date"
          label="Date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
        />
      </div>

      <div className="flex gap-2">
        <Button onClick={handleApply} size="sm">
          Apply Filters
        </Button>
        <Button onClick={handleReset} variant="outline" size="sm">
          Reset
        </Button>
      </div>
    </div>
  );
}
