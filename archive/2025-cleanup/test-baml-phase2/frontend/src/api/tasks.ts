/**
 * API client for task management operations.
 * Abstraction layer for all backend communication.
 */

import { Task, CreateTaskInput, UpdateTaskInput } from '../types/task';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/**
 * Helper function to handle API responses and errors.
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
  }

  // Handle 204 No Content responses
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

/**
 * Fetch all tasks from the API.
 */
export async function getTasks(): Promise<Task[]> {
  const response = await fetch(`${API_BASE_URL}/tasks`, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  return handleResponse<Task[]>(response);
}

/**
 * Create a new task.
 */
export async function createTask(task: CreateTaskInput): Promise<Task> {
  const response = await fetch(`${API_BASE_URL}/tasks`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(task),
  });

  return handleResponse<Task>(response);
}

/**
 * Update an existing task.
 */
export async function updateTask(id: number, task: UpdateTaskInput): Promise<Task> {
  const response = await fetch(`${API_BASE_URL}/tasks/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(task),
  });

  return handleResponse<Task>(response);
}

/**
 * Delete a task.
 */
export async function deleteTask(id: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/tasks/${id}`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  return handleResponse<void>(response);
}
