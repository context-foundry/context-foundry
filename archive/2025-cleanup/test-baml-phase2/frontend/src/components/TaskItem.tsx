/**
 * TaskItem component for displaying and interacting with individual tasks.
 */

import React, { useState } from 'react';
import { Task, UpdateTaskInput } from '../types/task';

interface TaskItemProps {
  task: Task;
  onUpdate: (id: number, updates: UpdateTaskInput) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
}

export default function TaskItem({ task, onUpdate, onDelete }: TaskItemProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(task.title);
  const [editDescription, setEditDescription] = useState(task.description);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleToggleComplete = async () => {
    setIsProcessing(true);
    setError(null);

    try {
      await onUpdate(task.id, { completed: !task.completed });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update task');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editTitle.trim()) {
      setError('Title cannot be empty');
      return;
    }

    setIsProcessing(true);
    setError(null);

    try {
      await onUpdate(task.id, {
        title: editTitle.trim(),
        description: editDescription.trim(),
      });
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update task');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleCancelEdit = () => {
    setEditTitle(task.title);
    setEditDescription(task.description);
    setIsEditing(false);
    setError(null);
  };

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this task?')) {
      return;
    }

    setIsProcessing(true);
    setError(null);

    try {
      await onDelete(task.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete task');
      setIsProcessing(false);
    }
  };

  if (isEditing) {
    return (
      <div className="task-item editing">
        <div className="task-edit-form">
          <input
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            disabled={isProcessing}
            className="form-input"
            maxLength={200}
          />
          <textarea
            value={editDescription}
            onChange={(e) => setEditDescription(e.target.value)}
            disabled={isProcessing}
            className="form-textarea"
            maxLength={1000}
            rows={3}
          />
          {error && <div className="error-message">{error}</div>}
          <div className="task-actions">
            <button
              onClick={handleSaveEdit}
              disabled={isProcessing || !editTitle.trim()}
              className="btn btn-primary btn-sm"
            >
              Save
            </button>
            <button
              onClick={handleCancelEdit}
              disabled={isProcessing}
              className="btn btn-secondary btn-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`task-item ${task.completed ? 'completed' : ''}`}>
      <div className="task-content">
        <label className="task-checkbox">
          <input
            type="checkbox"
            checked={task.completed}
            onChange={handleToggleComplete}
            disabled={isProcessing}
          />
          <span className="task-title">{task.title}</span>
        </label>
        {task.description && (
          <p className="task-description">{task.description}</p>
        )}
        <div className="task-meta">
          <span className="task-date">
            Created: {new Date(task.created_at).toLocaleString()}
          </span>
        </div>
        {error && <div className="error-message">{error}</div>}
      </div>
      <div className="task-actions">
        <button
          onClick={() => setIsEditing(true)}
          disabled={isProcessing}
          className="btn btn-secondary btn-sm"
        >
          Edit
        </button>
        <button
          onClick={handleDelete}
          disabled={isProcessing}
          className="btn btn-danger btn-sm"
        >
          Delete
        </button>
      </div>
    </div>
  );
}
