import { useState, useEffect } from 'react';
import type { Phase, Artifact } from '../../types';
import * as api from '../../api/client';

interface ArtifactEditorProps {
  jobId: string;
  phase: Phase;
}

export function ArtifactEditor({ jobId, phase }: ArtifactEditorProps) {
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<Artifact | null>(null);
  const [editedContent, setEditedContent] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    // TODO: Fetch artifacts for this job/phase
    // For now, show placeholder
    setArtifacts([]);
    setSelectedArtifact(null);
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
