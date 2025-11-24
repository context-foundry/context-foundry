/**
 * TaskList component - container for task management.
 * Manages state and coordinates between TaskForm and TaskItem components.
 */

import React, { useState, useEffect } from 'react';
import { Task, CreateTaskInput, UpdateTaskInput } from '../types/task';
import * as tasksApi from '../api/tasks';
import TaskForm from './TaskForm';
import TaskItem from './TaskItem';

export default function TaskList() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load tasks on component mount
  useEffect(() => {
    loadTasks();
  }, []);

  const loadTasks = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const fetchedTasks = await tasksApi.getTasks();
      setTasks(fetchedTasks);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tasks');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateTask = async (taskData: CreateTaskInput) => {
    const newTask = await tasksApi.createTask(taskData);
    setTasks([newTask, ...tasks]);
  };

  const handleUpdateTask = async (id: number, updates: UpdateTaskInput) => {
    const updatedTask = await tasksApi.updateTask(id, updates);
    setTasks(tasks.map(task => task.id === id ? updatedTask : task));
  };

  const handleDeleteTask = async (id: number) => {
    await tasksApi.deleteTask(id);
    setTasks(tasks.filter(task => task.id !== id));
  };

  if (isLoading) {
    return (
      <div className="task-list-container">
        <div className="loading">Loading tasks...</div>
      </div>
    );
  }

  return (
    <div className="task-list-container">
      <h1>Task Manager</h1>

      {error && (
        <div className="error-banner">
          {error}
          <button onClick={loadTasks} className="btn btn-sm">
            Retry
          </button>
        </div>
      )}

      <section className="task-form-section">
        <h2>Add New Task</h2>
        <TaskForm onSubmit={handleCreateTask} />
      </section>

      <section className="task-list-section">
        <h2>Tasks ({tasks.length})</h2>

        {tasks.length === 0 ? (
          <div className="empty-state">
            <p>No tasks yet. Create your first task above!</p>
          </div>
        ) : (
          <div className="task-list">
            {tasks.map(task => (
              <TaskItem
                key={task.id}
                task={task}
                onUpdate={handleUpdateTask}
                onDelete={handleDeleteTask}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
