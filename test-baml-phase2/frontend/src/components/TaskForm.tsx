/**
 * TaskForm component for creating new tasks.
 */

import React, { useState } from 'react';
import { CreateTaskInput } from '../types/task';

interface TaskFormProps {
  onSubmit: (task: CreateTaskInput) => Promise<void>;
}

export default function TaskForm({ onSubmit }: TaskFormProps) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!title.trim()) {
      setError('Title is required');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await onSubmit({
        title: title.trim(),
        description: description.trim(),
      });

      // Clear form on success
      setTitle('');
      setDescription('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create task');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="task-form">
      <div className="form-group">
        <input
          type="text"
          placeholder="Task title *"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          disabled={isSubmitting}
          className="form-input"
          maxLength={200}
        />
      </div>

      <div className="form-group">
        <textarea
          placeholder="Task description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={isSubmitting}
          className="form-textarea"
          maxLength={1000}
          rows={3}
        />
      </div>

      {error && <div className="error-message">{error}</div>}

      <button
        type="submit"
        disabled={isSubmitting || !title.trim()}
        className="btn btn-primary"
      >
        {isSubmitting ? 'Adding...' : 'Add Task'}
      </button>
    </form>
  );
}
