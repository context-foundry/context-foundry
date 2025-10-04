/**
 * Todo App Frontend
 * Handles UI interactions and API communication
 */

// Configuration
const API_BASE = 'http://localhost:5000/api';
const FILTER_ALL = 'all';
const FILTER_ACTIVE = 'active';
const FILTER_COMPLETED = 'completed';

// State
let todos = [];
let currentFilter = FILTER_ALL;

// DOM Elements
const addTodoForm = document.getElementById('add-todo-form');
const todoTitleInput = document.getElementById('todo-title');
const todoDescriptionInput = document.getElementById('todo-description');
const todoList = document.getElementById('todo-list');
const loadingElement = document.getElementById('loading');
const errorMessageElement = document.getElementById('error-message');
const emptyStateElement = document.getElementById('empty-state');
const filterButtons = document.querySelectorAll('.filter-btn');
const toast = document.getElementById('toast');

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadTodos();
});

/**
 * Set up all event listeners
 */
function setupEventListeners() {
    addTodoForm.addEventListener('submit', handleAddTodo);
    
    filterButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const filter = btn.getAttribute('data-filter');
            setFilter(filter);
        });
    });
    
    // Event delegation for dynamic todo items
    todoList.addEventListener('change', handleTodoCheckbox);
    todoList.addEventListener('click', handleTodoDelete);
}

/**
 * Load todos from API
 */
async function loadTodos() {
    showLoading();
    hideError();
    
    try {
        const response = await fetch(`${API_BASE}/todos`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        todos = data.todos || [];
        renderTodos();
        
    } catch (error) {
        console.error('Failed to load todos:', error);
        showError('Failed to load todos. Please check your connection and try again.');
    } finally {
        hideLoading();
    }
}

/**
 * Handle add todo form submission
 */
async function handleAddTodo(event) {
    event.preventDefault();
    
    const title = todoTitleInput.value.trim();
    const description = todoDescriptionInput.value.trim();
    
    if (!title) {
        showToast('Please enter a title', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/todos`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ title, description })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Failed to create todo');
        }
        
        const data = await response.json();
        todos.push(data.todo);
        
        // Clear form
        todoTitleInput.value = '';
        todoDescriptionInput.value = '';
        
        renderTodos();
        showToast('Todo added successfully!', 'success');
        
    } catch (error) {
        console.error('Failed to add todo:', error);
        showToast(error.message, 'error');
    }
}

/**
 * Handle todo checkbox change (complete/uncomplete)
 */
async function handleTodoCheckbox(event) {
    if (!event.target.classList.contains('todo-checkbox')) {
        return;
    }
    
    const todoId = event.target.getAttribute('data-id');
    const isChecked = event.target.checked;
    
    if (!isChecked) {
        // Prevent unchecking - todos can only be marked as complete
        event.target.checked = true;
        showToast('Todos cannot be uncompleted', 'error');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/todos/${todoId}/complete`, {
            method: 'PUT'
        });
        
        if (!response.ok) {
            throw new Error('Failed to complete todo');
        }
        
        const data = await response.json();
        
        // Update local state
        const todoIndex = todos.findIndex(t => t.id === todoId);
        if (todoIndex !== -1) {
            todos[todoIndex] = data.todo;
        }
        
        renderTodos();
        showToast('Todo completed!', 'success');
        
    } catch (error) {
        console.error('Failed to complete todo:', error);
        event.target.checked = false;
        showToast('Failed to complete todo', 'error');
    }
}

/**
 * Handle delete button click
 */
async function handleTodoDelete(event) {
    if (!event.target.classList.contains('btn-delete')) {
        return;
    }
    
    const todoId = event.target.getAttribute('data-id');
    
    if (!confirm('Are you sure you want to delete this todo?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/todos/${todoId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Failed to delete todo');
        }
        
        // Remove from local state
        todos = todos.filter(t => t.id !== todoId);
        
        renderTodos();
        showToast('Todo deleted', 'success');
        
    } catch (error) {
        console.error('Failed to delete todo:', error);
        showToast('Failed to delete todo', 'error');
    }
}

/**
 * Set active filter
 */
function setFilter(filter) {
    currentFilter = filter;
    
    // Update button states
    filterButtons.forEach(btn => {
        if (btn.getAttribute('data-filter') === filter) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
    
    renderTodos();
}

/**
 * Render todos based on current filter
 */
function renderTodos() {
    const filteredTodos = getFilteredTodos();
    
    if (filteredTodos.length === 0) {
        showEmptyState();
        todoList.innerHTML = '';
        return;
    }
    
    hideEmptyState();
    
    todoList.innerHTML = filteredTodos.map(todo => `
        <li class="todo-item ${todo.completed ? 'completed' : ''}">
            <input 
                type="checkbox" 
                class="todo-checkbox" 
                data-id="${todo.id}"
                ${todo.completed ? 'checked' : ''}
            >
            <div class="todo-content">
                <h3>${escapeHtml(todo.title)}</h3>
                ${todo.description ? `<p>${escapeHtml(todo.description)}</p>` : ''}
                <div class="todo-meta">
                    Created: ${formatDate(todo.created_at)}
                    ${todo.completed_at ? ` • Completed: ${formatDate(todo.completed_at)}` : ''}
                </div>
            </div>
            <div class="todo-actions">
                <button class="btn-delete" data-id="${todo.id}">Delete</button>
            </div>
        </li>
    `).join('');
}

/**
 * Get filtered todos based on current filter
 */
function getFilteredTodos() {
    switch (currentFilter) {
        case FILTER_ACTIVE:
            return todos.filter(t => !t.completed);
        case FILTER_COMPLETED:
            return todos.filter(t => t.completed);
        default:
            return todos;
    }
}

/**
 * Format ISO date string to readable format
 */
function formatDate(isoString) {
    const date = new Date(isoString);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Show loading state
 */
function showLoading() {
    loadingElement.classList.remove('hidden');
}

/**
 * Hide loading state
 */
function hideLoading() {
    loadingElement.classList.add('hidden');
}

/**
 * Show error message
 */
function showError(message) {
    errorMessageElement.textContent = message;
    errorMessageElement.classList.remove('hidden');
}

/**
 * Hide error message
 */
function hideError() {
    errorMessageElement.classList.add('hidden');
}

/**
 * Show empty state
 */
function showEmptyState() {
    emptyStateElement.classList.remove('hidden');
}

/**
 * Hide empty state
 */
function hideEmptyState() {
    emptyStateElement.classList.add('hidden');
}

/**
 * Show toast notification
 */
function showToast(message, type = 'success') {
    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.remove('hidden');
    
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}