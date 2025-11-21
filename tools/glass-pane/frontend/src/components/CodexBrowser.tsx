import { useEffect, useState } from 'react';

interface CodexEntry {
  id: string;
  type: string;
  title: string;
  description: string;
  severity?: string;
  category?: string;
  tags: string[];
  project_types: string[];
  frequency?: number;
  confidence?: number;
  created_at?: string;
  updated_at?: string;
  status?: string;
}

interface CodexEntryDetail extends CodexEntry {
  solutions: Array<{
    description: string;
    steps?: string[];
    code?: string;
  }>;
  evidence: string[];
  implementation_code?: string;
  requirements: string[];
  example?: string;
  file_type?: string;
  file_path?: string;
}

interface CodexStats {
  total_entries: number;
  entries_by_type: Record<string, number>;
  total_issues: number;
  total_patterns: number;
  total_skills: number;
  total_learnings: number;
}

export default function CodexBrowser() {
  const [stats, setStats] = useState<CodexStats | null>(null);
  const [entries, setEntries] = useState<CodexEntry[]>([]);
  const [selectedEntry, setSelectedEntry] = useState<CodexEntryDetail | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterCategory, setFilterCategory] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch stats on mount
  useEffect(() => {
    fetchStats();
    fetchEntries();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await fetch('/api/codex/stats');
      if (!response.ok) throw new Error('Failed to fetch stats');
      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error('Error fetching stats:', err);
      setError(err instanceof Error ? err.message : 'Failed to load stats');
    }
  };

  const fetchEntries = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filterType) params.append('entry_type', filterType);
      if (filterCategory) params.append('category', filterCategory);
      if (filterSeverity) params.append('severity', filterSeverity);
      params.append('limit', '100');

      const response = await fetch(`/api/codex/entries?${params.toString()}`);
      if (!response.ok) throw new Error('Failed to fetch entries');
      const data = await response.json();
      setEntries(data);
    } catch (err) {
      console.error('Error fetching entries:', err);
      setError(err instanceof Error ? err.message : 'Failed to load entries');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      fetchEntries();
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.append('q', searchQuery);
      if (filterType) params.append('entry_type', filterType);
      if (filterCategory) params.append('category', filterCategory);
      if (filterSeverity) params.append('severity', filterSeverity);

      const response = await fetch(`/api/codex/search?${params.toString()}`);
      if (!response.ok) throw new Error('Search failed');
      const data = await response.json();
      setEntries(data.results);
    } catch (err) {
      console.error('Error searching:', err);
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  const fetchEntryDetail = async (entryId: string) => {
    try {
      const response = await fetch(`/api/codex/entry/${entryId}`);
      if (!response.ok) throw new Error('Failed to fetch entry details');
      const data = await response.json();
      setSelectedEntry(data);
    } catch (err) {
      console.error('Error fetching entry details:', err);
      setError(err instanceof Error ? err.message : 'Failed to load entry details');
    }
  };

  const getTypeIcon = (typeStr: string): string => {
    switch (typeStr) {
      case 'issue': return 'ISS';
      case 'pattern': return 'PAT';
      case 'skill': return 'SKL';
      case 'learning': return 'LRN';
      default: return 'DOC';
    }
  };

  const getSeverityColor = (severity?: string): string => {
    switch (severity?.toLowerCase()) {
      case 'critical': return 'text-red-500';
      case 'high': return 'text-orange-500';
      case 'medium': return 'text-yellow-500';
      case 'low': return 'text-blue-500';
      default: return 'text-gray-500';
    }
  };

  const getSeverityBadge = (severity?: string): string => {
    switch (severity?.toLowerCase()) {
      case 'critical': return 'bg-red-900/30 text-red-400 border-red-700';
      case 'high': return 'bg-orange-900/30 text-orange-400 border-orange-700';
      case 'medium': return 'bg-yellow-900/30 text-yellow-400 border-yellow-700';
      case 'low': return 'bg-blue-900/30 text-blue-400 border-blue-700';
      default: return 'bg-gray-800 text-gray-400 border-gray-700';
    }
  };

  const formatText = (text: string) => {
    if (!text) return null;

    // Split into paragraphs (double newline or numbered items)
    const paragraphs = text.split(/\n\n+/);

    return paragraphs.map((para, idx) => {
      // Check if it's a code block
      if (para.trim().startsWith('```')) {
        const code = para.replace(/```\w*\n?/g, '').trim();
        return (
          <pre key={idx} className="my-3 p-3 bg-gray-900 rounded text-xs text-gray-300 overflow-x-auto border border-gray-700">
            <code>{code}</code>
          </pre>
        );
      }

      // Check if it's a bulleted list
      if (para.includes('\n- ') || para.startsWith('- ')) {
        const items = para.split('\n').filter(line => line.trim());
        return (
          <ul key={idx} className="my-2 ml-4 list-disc space-y-1 text-sm text-gray-300">
            {items.map((item, i) => (
              <li key={i}>{item.replace(/^-\s*/, '')}</li>
            ))}
          </ul>
        );
      }

      // Check if it's a numbered list
      if (/^\d+\./.test(para.trim())) {
        const items = para.split(/\n(?=\d+\.)/).filter(line => line.trim());
        return (
          <ol key={idx} className="my-2 ml-4 list-decimal space-y-1 text-sm text-gray-300">
            {items.map((item, i) => (
              <li key={i}>{item.replace(/^\d+\.\s*/, '')}</li>
            ))}
          </ol>
        );
      }

      // Regular paragraph - split by single newlines for line breaks
      const lines = para.split('\n').filter(line => line.trim());
      return (
        <p key={idx} className="my-2 text-sm text-gray-300 leading-relaxed">
          {lines.map((line, i) => (
            <span key={i}>
              {line}
              {i < lines.length - 1 && <br />}
            </span>
          ))}
        </p>
      );
    });
  };

  return (
    <div className="h-full flex flex-col bg-gray-950">
      {/* Stats Header */}
      {stats && (
        <div className="p-4 bg-gray-900 border-b border-gray-800">
          <div className="grid grid-cols-5 gap-4">
            <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
              <div className="text-2xl font-bold text-cyan-400">{stats.total_entries}</div>
              <div className="text-xs text-gray-400">Total Entries</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
              <div className="text-2xl font-bold text-red-400">{stats.total_issues}</div>
              <div className="text-xs text-gray-400">Issues</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
              <div className="text-2xl font-bold text-purple-400">{stats.total_patterns}</div>
              <div className="text-xs text-gray-400">Patterns</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
              <div className="text-2xl font-bold text-yellow-400">{stats.total_skills}</div>
              <div className="text-xs text-gray-400">Skills</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-3 border border-gray-700">
              <div className="text-2xl font-bold text-green-400">{stats.total_learnings}</div>
              <div className="text-xs text-gray-400">Learnings</div>
            </div>
          </div>
        </div>
      )}

      {/* Search and Filters */}
      <div className="p-4 bg-gray-900 border-b border-gray-800">
        <div className="flex gap-2 mb-3">
          <input
            type="text"
            placeholder="Search codex..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-cyan-500"
          />
          <button
            onClick={handleSearch}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded text-sm font-medium transition-colors"
          >
            Search
          </button>
          <button
            onClick={() => {
              setSearchQuery('');
              setFilterType('');
              setFilterCategory('');
              setFilterSeverity('');
              fetchEntries();
            }}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded text-sm font-medium transition-colors"
          >
            Clear
          </button>
        </div>

        <div className="flex gap-2">
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-cyan-500"
          >
            <option value="">All Types</option>
            <option value="issue">Issues</option>
            <option value="pattern">Patterns</option>
            <option value="skill">Skills</option>
            <option value="learning">Learnings</option>
          </select>

          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-100 focus:outline-none focus:border-cyan-500"
          >
            <option value="">All Severities</option>
            <option value="CRITICAL">Critical</option>
            <option value="HIGH">High</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>

          <input
            type="text"
            placeholder="Category filter..."
            value={filterCategory}
            onChange={(e) => setFilterCategory(e.target.value)}
            className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-cyan-500"
          />

          <button
            onClick={fetchEntries}
            className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded text-sm transition-colors"
          >
            Apply Filters
          </button>
        </div>
      </div>

      {error && (
        <div className="mx-4 mt-4 p-3 bg-red-900/20 border border-red-700 rounded text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Content Area */}
      <div className="flex-1 flex gap-4 p-4 overflow-hidden">
        {/* Entries List */}
        <div className="w-1/2 flex flex-col bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <div className="p-3 border-b border-gray-800 bg-gray-900/50">
            <h3 className="font-semibold text-gray-100">
              {loading ? 'Loading...' : `${entries.length} Entries`}
            </h3>
          </div>
          <div className="flex-1 overflow-y-auto">
            {entries.map((entry) => (
              <div
                key={entry.id}
                onClick={() => fetchEntryDetail(entry.id)}
                className={`p-3 border-b border-gray-800 cursor-pointer hover:bg-gray-800/50 transition-colors ${
                  selectedEntry?.id === entry.id ? 'bg-gray-800' : ''
                }`}
              >
                <div className="flex items-start gap-2">
                  <span className="text-xs font-mono px-2 py-1 bg-cyan-900/30 text-cyan-400 border border-cyan-700 rounded">{getTypeIcon(entry.type)}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="font-medium text-gray-100 truncate">{entry.title}</h4>
                      {entry.severity && (
                        <span className={`text-xs px-2 py-0.5 rounded border ${getSeverityBadge(entry.severity)}`}>
                          {entry.severity}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-400 line-clamp-2">{entry.description}</p>
                    <div className="flex items-center gap-2 mt-2 text-xs text-gray-500">
                      <span className="px-2 py-0.5 bg-gray-800 rounded">{entry.type}</span>
                      {entry.frequency && <span>Seen {entry.frequency}x</span>}
                      {entry.confidence && <span>Confidence: {(entry.confidence * 100).toFixed(0)}%</span>}
                    </div>
                  </div>
                </div>
              </div>
            ))}
            {entries.length === 0 && !loading && (
              <div className="p-8 text-center text-gray-500">
                No entries found. Try adjusting your search or filters.
              </div>
            )}
          </div>
        </div>

        {/* Entry Details */}
        <div className="w-1/2 flex flex-col bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          <div className="p-3 border-b border-gray-800 bg-gray-900/50">
            <h3 className="font-semibold text-gray-100">Details</h3>
          </div>
          <div className="flex-1 overflow-y-auto p-4">
            {selectedEntry ? (
              <div className="space-y-4">
                {/* Header */}
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-mono font-bold px-2 py-1 bg-cyan-900/30 text-cyan-400 border border-cyan-700 rounded">{getTypeIcon(selectedEntry.type)}</span>
                    <h2 className="text-xl font-bold text-gray-100">{selectedEntry.title}</h2>
                  </div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xs px-2 py-1 bg-gray-800 rounded">{selectedEntry.type}</span>
                    {selectedEntry.severity && (
                      <span className={`text-xs px-2 py-1 rounded border ${getSeverityBadge(selectedEntry.severity)}`}>
                        {selectedEntry.severity}
                      </span>
                    )}
                    {selectedEntry.category && (
                      <span className="text-xs px-2 py-1 bg-purple-900/30 text-purple-400 border border-purple-700 rounded">
                        {selectedEntry.category}
                      </span>
                    )}
                  </div>
                </div>

                {/* Description */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-300 mb-2">Description</h3>
                  <div className="text-sm text-gray-400">
                    {formatText(selectedEntry.description)}
                  </div>
                </div>

                {/* Metadata */}
                {(selectedEntry.frequency || selectedEntry.confidence) && (
                  <div className="grid grid-cols-2 gap-3">
                    {selectedEntry.frequency && (
                      <div className="bg-gray-800 rounded p-3">
                        <div className="text-xs text-gray-500">Frequency</div>
                        <div className="text-lg font-bold text-cyan-400">{selectedEntry.frequency}</div>
                      </div>
                    )}
                    {selectedEntry.confidence !== undefined && (
                      <div className="bg-gray-800 rounded p-3">
                        <div className="text-xs text-gray-500">Confidence</div>
                        <div className="text-lg font-bold text-green-400">
                          {(selectedEntry.confidence * 100).toFixed(0)}%
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Tags */}
                {selectedEntry.tags.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-300 mb-2">Tags</h3>
                    <div className="flex flex-wrap gap-2">
                      {selectedEntry.tags.map((tag) => (
                        <span key={tag} className="text-xs px-2 py-1 bg-cyan-900/30 text-cyan-400 border border-cyan-700 rounded">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Project Types */}
                {selectedEntry.project_types.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-300 mb-2">Project Types</h3>
                    <div className="flex flex-wrap gap-2">
                      {selectedEntry.project_types.map((type) => (
                        <span key={type} className="text-xs px-2 py-1 bg-gray-800 text-gray-400 rounded">
                          {type}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Solutions */}
                {selectedEntry.solutions.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-300 mb-2">Solutions</h3>
                    <div className="space-y-3">
                      {selectedEntry.solutions.map((solution, idx) => (
                        <div key={idx} className="bg-gray-800 rounded p-3 border border-gray-700">
                          <div className="text-sm text-gray-300">
                            {formatText(solution.description)}
                          </div>
                          {solution.steps && (
                            <ol className="mt-2 ml-4 list-decimal text-xs text-gray-400 space-y-1">
                              {solution.steps.map((step, stepIdx) => (
                                <li key={stepIdx}>{step}</li>
                              ))}
                            </ol>
                          )}
                          {solution.code && (
                            <pre className="mt-2 p-2 bg-gray-900 rounded text-xs text-gray-300 overflow-x-auto border border-gray-700">
                              <code>{solution.code}</code>
                            </pre>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Implementation Code (for skills) */}
                {selectedEntry.implementation_code && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-300 mb-2">Implementation</h3>
                    <pre className="p-3 bg-gray-800 rounded text-xs text-gray-300 overflow-x-auto">
                      {selectedEntry.implementation_code}
                    </pre>
                  </div>
                )}

                {/* Requirements */}
                {selectedEntry.requirements.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-300 mb-2">Requirements</h3>
                    <ul className="ml-4 list-disc text-sm text-gray-400 space-y-1">
                      {selectedEntry.requirements.map((req, idx) => (
                        <li key={idx}>{req}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Example */}
                {selectedEntry.example && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-300 mb-2">Example</h3>
                    <pre className="p-3 bg-gray-800 rounded text-xs text-gray-300 overflow-x-auto">
                      {selectedEntry.example}
                    </pre>
                  </div>
                )}

                {/* Evidence */}
                {selectedEntry.evidence.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-gray-300 mb-2">Evidence</h3>
                    <ul className="ml-4 list-disc text-xs text-gray-400 space-y-1">
                      {selectedEntry.evidence.map((ev, idx) => (
                        <li key={idx}>{ev}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Metadata */}
                <div className="text-xs text-gray-500 pt-3 border-t border-gray-800">
                  <div>ID: {selectedEntry.id}</div>
                  {selectedEntry.created_at && <div>Created: {new Date(selectedEntry.created_at).toLocaleString()}</div>}
                  {selectedEntry.updated_at && <div>Updated: {new Date(selectedEntry.updated_at).toLocaleString()}</div>}
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-gray-500">
                Select an entry to view details
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
