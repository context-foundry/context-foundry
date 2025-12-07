import { useState, useCallback, useEffect } from 'react';

interface SearchBoxProps {
  placeholder?: string;
  onSearch: (query: string) => void;
  matchCount?: number;
  currentMatch?: number;
  onNavigate?: (direction: 'prev' | 'next') => void;
  debounceMs?: number;
}

export function SearchBox({
  placeholder = 'Search...',
  onSearch,
  matchCount = 0,
  currentMatch = 0,
  onNavigate,
  debounceMs = 200,
}: SearchBoxProps) {
  const [query, setQuery] = useState('');

  // Debounce the search
  useEffect(() => {
    const timer = setTimeout(() => {
      onSearch(query);
    }, debounceMs);
    return () => clearTimeout(timer);
  }, [query, onSearch, debounceMs]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && onNavigate) {
        e.preventDefault();
        onNavigate(e.shiftKey ? 'prev' : 'next');
      } else if (e.key === 'Escape') {
        setQuery('');
        onSearch('');
      }
    },
    [onNavigate, onSearch]
  );

  const handleClear = () => {
    setQuery('');
    onSearch('');
  };

  return (
    <div className="search-box">
      <div className="search-box-input-wrapper">
        <svg
          className="search-box-icon"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <circle cx="11" cy="11" r="8" />
          <path d="M21 21l-4.35-4.35" />
        </svg>
        <input
          type="text"
          className="search-box-input"
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        {query && (
          <button
            className="search-box-clear"
            onClick={handleClear}
            title="Clear search (Esc)"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" />
            </svg>
          </button>
        )}
      </div>
      {query && matchCount > 0 && (
        <div className="search-box-results">
          <span className="search-box-count">
            {currentMatch}/{matchCount}
          </span>
          {onNavigate && (
            <div className="search-box-nav">
              <button
                className="search-box-nav-btn"
                onClick={() => onNavigate('prev')}
                title="Previous match (Shift+Enter)"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 19V5M5 12l7-7 7 7" stroke="currentColor" strokeWidth="2" fill="none" />
                </svg>
              </button>
              <button
                className="search-box-nav-btn"
                onClick={() => onNavigate('next')}
                title="Next match (Enter)"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 5v14M19 12l-7 7-7-7" stroke="currentColor" strokeWidth="2" fill="none" />
                </svg>
              </button>
            </div>
          )}
        </div>
      )}
      {query && matchCount === 0 && (
        <span className="search-box-no-results">No matches</span>
      )}
    </div>
  );
}

// Utility function to highlight text with search matches
export function highlightText(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text;

  const regex = new RegExp(`(${escapeRegExp(query)})`, 'gi');
  const parts = text.split(regex);

  return parts.map((part, i) =>
    regex.test(part) ? (
      <mark key={i} className="search-highlight">
        {part}
      </mark>
    ) : (
      part
    )
  );
}

function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
