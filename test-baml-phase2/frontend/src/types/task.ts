/**
 * TypeScript interfaces for Task domain models.
 * These match the backend Pydantic models for type safety.
 */

export interface Task {
  id: number;
  title: string;
  description: string;
  completed: boolean;
  created_at: string;  // ISO 8601 datetime string
  updated_at: string;  // ISO 8601 datetime string
}

export interface CreateTaskInput {
  title: string;
  description: string;
}

export interface UpdateTaskInput {
  title?: string;
  description?: string;
  completed?: boolean;
}
