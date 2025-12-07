import { useState, useEffect } from 'react';
import type { Phase } from '../../types';
import * as api from '../../api/client';

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

  if (isLoading) {
    return (
      <div className="artifact-editor-empty">
        Loading artifacts...
      </div>
    );
  }

  if (error) {
    return (
      <div className="artifact-editor-empty">
        {error}
      </div>
    );
  }

  if (artifacts.length === 0) {
    return (
      <div className="artifact-editor-empty">
        No artifacts for this phase
      </div>
    );
  }

  return (
    <div className="artifact-editor">
      <div className="artifact-tabs">
        {artifacts.map((artifact) => (
          <button
            key={artifact.id}
            className={`artifact-tab ${selectedArtifact?.id === artifact.id ? 'active' : ''}`}
            onClick={() => {
              setSelectedArtifact(artifact);
              setIsEditing(false);
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
            <textarea
              className="artifact-textarea"
              value={editedContent}
              onChange={(e) => setEditedContent(e.target.value)}
              spellCheck={false}
            />
          ) : (
            <pre className="artifact-code">
              <code>{selectedArtifact.content}</code>
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
