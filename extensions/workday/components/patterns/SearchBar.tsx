'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Search, X } from 'lucide-react';

interface SearchBarProps {
  onSearch: (query: string) => void;
  placeholder?: string;
  debounceMs?: number;
}

export function SearchBar({
  onSearch,
  placeholder = 'Search patterns...',
  debounceMs = 300,
}: SearchBarProps) {
  const [query, setQuery] = useState('');

  const debouncedSearch = useCallback(
    (value: string) => {
      const timer = setTimeout(() => {
        onSearch(value);
      }, debounceMs);

      return () => clearTimeout(timer);
    },
    [onSearch, debounceMs]
  );

  useEffect(() => {
    const cleanup = debouncedSearch(query);
    return cleanup;
  }, [query, debouncedSearch]);

  const handleClear = () => {
    setQuery('');
    onSearch('');
  };

  return (
    <div className="relative w-full">
      <label htmlFor="pattern-search" className="sr-only">
        Search patterns
      </label>
      <div className="relative">
        <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none">
          <Search className="h-5 w-5 text-gray-400" aria-hidden="true" />
        </div>
        <input
          id="pattern-search"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={placeholder}
          className="block w-full pl-10 pr-10 py-2.5 border border-gray-300 rounded-lg text-sm text-gray-900 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-[44px]"
          aria-label="Search patterns"
        />
        {query && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute inset-y-0 right-0 flex items-center pr-3 hover:bg-gray-50 rounded-r-lg transition-colors"
            aria-label="Clear search"
          >
            <X className="h-5 w-5 text-gray-400 hover:text-gray-600" aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  );
}
