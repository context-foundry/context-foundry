/**
 * Tests for TaskList component.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TaskList from '../src/components/TaskList';
import * as tasksApi from '../src/api/tasks';

// Mock the API module
vi.mock('../src/api/tasks');

describe('TaskList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    vi.mocked(tasksApi.getTasks).mockImplementation(() => new Promise(() => {}));
    render(<TaskList />);
    expect(screen.getByText(/loading tasks/i)).toBeInTheDocument();
  });

  it('displays tasks from API', async () => {
    const mockTasks = [
      {
        id: 1,
        title: 'Test Task',
        description: 'Test Description',
        completed: false,
        created_at: '2025-01-01T10:00:00',
        updated_at: '2025-01-01T10:00:00',
      },
    ];

    vi.mocked(tasksApi.getTasks).mockResolvedValue(mockTasks);

    render(<TaskList />);

    await waitFor(() => {
      expect(screen.getByText('Test Task')).toBeInTheDocument();
      expect(screen.getByText('Test Description')).toBeInTheDocument();
    });
  });

  it('displays empty state when no tasks', async () => {
    vi.mocked(tasksApi.getTasks).mockResolvedValue([]);

    render(<TaskList />);

    await waitFor(() => {
      expect(screen.getByText(/no tasks yet/i)).toBeInTheDocument();
    });
  });

  it('handles API error gracefully', async () => {
    vi.mocked(tasksApi.getTasks).mockRejectedValue(new Error('Network error'));

    render(<TaskList />);

    await waitFor(() => {
      expect(screen.getByText(/network error/i)).toBeInTheDocument();
    });
  });

  it('creates new task via form', async () => {
    const user = userEvent.setup();
    const mockTasks: any[] = [];

    vi.mocked(tasksApi.getTasks).mockResolvedValue(mockTasks);
    vi.mocked(tasksApi.createTask).mockResolvedValue({
      id: 1,
      title: 'New Task',
      description: 'New Description',
      completed: false,
      created_at: '2025-01-01T10:00:00',
      updated_at: '2025-01-01T10:00:00',
    });

    render(<TaskList />);

    await waitFor(() => {
      expect(screen.getByText(/no tasks yet/i)).toBeInTheDocument();
    });

    const titleInput = screen.getByPlaceholderText(/task title/i);
    const descriptionInput = screen.getByPlaceholderText(/task description/i);
    const addButton = screen.getByRole('button', { name: /add task/i });

    await user.type(titleInput, 'New Task');
    await user.type(descriptionInput, 'New Description');
    await user.click(addButton);

    await waitFor(() => {
      expect(tasksApi.createTask).toHaveBeenCalledWith({
        title: 'New Task',
        description: 'New Description',
      });
    });
  });
});
