import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import type { Phase } from '../../types';
import * as api from '../../api/client';
import { CollapsibleSection } from '../common/CollapsibleSection';
import { SearchBox } from '../common/SearchBox';

interface ArtifactEditorProps {
  jobId: string;
  phase: Phase;
}

// Local artifact type that matches API response
interface LocalArtifact {
  id: string;
  name: string;
  path: string;
  type: string;
  content: string;
  size: number;
}

export function ArtifactEditor({ jobId, phase }: ArtifactEditorProps) {
  const [artifacts, setArtifacts] = useState<LocalArtifact[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<LocalArtifact | null>(null);
  const [editedContent, setEditedContent] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [currentMatchIndex, setCurrentMatchIndex] = useState(0);
  const contentRef = useRef<HTMLPreElement | HTMLTextAreaElement | null>(null);
  const matchRefs = useRef<(HTMLElement | null)[]>([]);

  useEffect(() => {
    async function fetchArtifacts() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await api.getJobArtifacts(jobId, phase);
        // Transform to local format with generated IDs
        const transformed: LocalArtifact[] = data.map((a, index) => ({
          id: `${phase}-${index}-${a.name}`,
          name: a.name,
          path: a.path,
          type: a.type,
          content: a.content,
          size: a.size,
        }));
        setArtifacts(transformed);
        if (transformed.length > 0) {
          setSelectedArtifact(transformed[0]);
        } else {
          setSelectedArtifact(null);
        }
      } catch (err) {
        console.error('Failed to fetch artifacts:', err);
        setError('Failed to load artifacts');
        setArtifacts([]);
        setSelectedArtifact(null);
      } finally {
        setIsLoading(false);
      }
    }

    fetchArtifacts();
  }, [jobId, phase]);

  // Calculate matches for current artifact
  const matches = useMemo(() => {
    if (!searchQuery.trim() || !selectedArtifact) return [];

    const content = isEditing ? editedContent : selectedArtifact.content;
    const results: number[] = [];
    const regex = new RegExp(escapeRegExp(searchQuery), 'gi');

    let match;
    while ((match = regex.exec(content)) !== null) {
      results.push(match.index);
    }

    return results;
  }, [selectedArtifact, editedContent, isEditing, searchQuery]);

  // Reset current match when query changes
  useEffect(() => {
    setCurrentMatchIndex(matches.length > 0 ? 1 : 0);
  }, [matches.length, searchQuery]);

  // Scroll to current match
  useEffect(() => {
    if (currentMatchIndex > 0 && matchRefs.current[currentMatchIndex - 1]) {
      matchRefs.current[currentMatchIndex - 1]?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [currentMatchIndex]);

  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query);
  }, []);

  const handleNavigate = useCallback((direction: 'prev' | 'next') => {
    if (matches.length === 0) return;

    setCurrentMatchIndex((prev) => {
      if (direction === 'next') {
        return prev >= matches.length ? 1 : prev + 1;
      } else {
        return prev <= 1 ? matches.length : prev - 1;
      }
    });
  }, [matches.length]);

  const handleEdit = () => {
    if (selectedArtifact) {
      setEditedContent(selectedArtifact.content);
      setIsEditing(true);
    }
  };

  const handleSave = async () => {
    if (!selectedArtifact) return;

    setIsSaving(true);
    try {
      await api.updateArtifact(jobId, selectedArtifact.id, editedContent);
      setSelectedArtifact({ ...selectedArtifact, content: editedContent });
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to save artifact:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditedContent('');
  };

  // Render content with search highlighting and line numbers
  const renderHighlightedContent = useCallback(() => {
    if (!selectedArtifact) return null;

    const content = isEditing ? editedContent : selectedArtifact.content;
    const lines = content.split('\n');

    if (!searchQuery.trim()) {
      return (
        <div className="code-with-lines">
          <div className="line-numbers" aria-hidden="true">
            {lines.map((_, i) => (
              <span key={i} className="line-number">{i + 1}</span>
            ))}
          </div>
          <code className="code-content">
            {lines.map((line, i) => (
              <span key={i} className="code-line">{line}{i < lines.length - 1 ? '\n' : ''}</span>
            ))}
          </code>
        </div>
      );
    }

    // With search highlighting
    const parts = splitWithHighlight(content, searchQuery);
    let matchIdx = 0;

    return (
      <div className="code-with-lines">
        <div className="line-numbers" aria-hidden="true">
          {lines.map((_, i) => (
            <span key={i} className="line-number">{i + 1}</span>
          ))}
        </div>
        <code className="code-content">
          {parts.map((part, i) => {
            if (part.isMatch) {
              matchIdx++;
              const isCurrentMatch = matchIdx === currentMatchIndex;
              return (
                <mark
                  key={i}
                  ref={(el) => {
                    if (el) matchRefs.current[matchIdx - 1] = el;
                  }}
                  className={`search-highlight ${isCurrentMatch ? 'current' : ''}`}
                >
                  {part.text}
                </mark>
              );
            }
            return <span key={i}>{part.text}</span>;
          })}
        </code>
      </div>
    );
  }, [selectedArtifact, isEditing, editedContent, searchQuery, currentMatchIndex]);

  // Render textarea with line numbers in edit mode
  const renderEditableContent = useCallback(() => {
    const lines = editedContent.split('\n');

    if (!searchQuery.trim()) {
      return (
        <div className="code-with-lines editable">
          <div className="line-numbers" aria-hidden="true">
            {lines.map((_, i) => (
              <span key={i} className="line-number">{i + 1}</span>
            ))}
          </div>
          <textarea
            ref={contentRef as React.RefObject<HTMLTextAreaElement>}
            className="artifact-textarea"
            value={editedContent}
            onChange={(e) => setEditedContent(e.target.value)}
            spellCheck={false}
          />
        </div>
      );
    }

    // In edit mode with search, show a split view:
    // - Editable textarea with line numbers
    // - Overlay with highlights (non-interactive)
    return (
      <div className="artifact-edit-search-container">
        <div className="code-with-lines editable">
          <div className="line-numbers" aria-hidden="true">
            {lines.map((_, i) => (
              <span key={i} className="line-number">{i + 1}</span>
            ))}
          </div>
          <textarea
            ref={contentRef as React.RefObject<HTMLTextAreaElement>}
            className="artifact-textarea artifact-textarea-searchable"
            value={editedContent}
            onChange={(e) => setEditedContent(e.target.value)}
            spellCheck={false}
          />
        </div>
        <div className="artifact-search-overlay">
          {renderHighlightedContent()}
        </div>
      </div>
    );
  }, [editedContent, searchQuery, renderHighlightedContent]);

  const searchHeader = (
    <SearchBox
      placeholder="Search files..."
      onSearch={handleSearch}
      matchCount={matches.length}
      currentMatch={currentMatchIndex}
      onNavigate={handleNavigate}
    />
  );

  if (isLoading) {
    return (
      <CollapsibleSection title="Files" headerContent={null}>
        <div className="artifact-editor-empty">
          Loading artifacts...
        </div>
      </CollapsibleSection>
    );
  }

  if (error) {
    return (
      <CollapsibleSection title="Files" headerContent={null}>
        <div className="artifact-editor-empty">
          {error}
        </div>
      </CollapsibleSection>
    );
  }

  if (artifacts.length === 0) {
    return (
      <CollapsibleSection title="Files" headerContent={null}>
        <div className="artifact-editor-empty">
          No artifacts for this phase
        </div>
      </CollapsibleSection>
    );
  }

  return (
    <CollapsibleSection title="Files" headerContent={searchHeader}>
      <div className="artifact-editor">
        <div className="artifact-tabs">
          {artifacts.map((artifact) => (
            <button
              key={artifact.id}
              className={`artifact-tab ${selectedArtifact?.id === artifact.id ? 'active' : ''}`}
              onClick={() => {
                setSelectedArtifact(artifact);
                setIsEditing(false);
                setSearchQuery(''); // Clear search when switching files
              }}
            >
              {artifact.path.split('/').pop()}
            </button>
          ))}
        </div>

        {selectedArtifact && (
          <div className="artifact-content">
            <div className="artifact-header">
              <span className="artifact-path">{selectedArtifact.path}</span>
              <div className="artifact-actions">
                {!isEditing ? (
                  <button className="btn" onClick={handleEdit}>
                    Edit
                  </button>
                ) : (
                  <>
                    <button
                      className="btn btn-primary"
                      onClick={handleSave}
                      disabled={isSaving}
                    >
                      {isSaving ? 'Saving...' : 'Save'}
                    </button>
                    <button className="btn" onClick={handleCancel}>
                      Cancel
                    </button>
                  </>
                )}
              </div>
            </div>

            {isEditing ? (
              renderEditableContent()
            ) : (
              <pre className="artifact-code" ref={contentRef as React.RefObject<HTMLPreElement>}>
                {renderHighlightedContent()}
              </pre>
            )}
          </div>
        )}
      </div>
    </CollapsibleSection>
  );
}

// Helper functions
function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function splitWithHighlight(text: string, query: string): { text: string; isMatch: boolean }[] {
  if (!query.trim()) return [{ text, isMatch: false }];

  const regex = new RegExp(`(${escapeRegExp(query)})`, 'gi');
  const parts = text.split(regex);

  return parts.filter(Boolean).map((part) => ({
    text: part,
    isMatch: regex.test(part) || part.toLowerCase() === query.toLowerCase(),
  }));
}
