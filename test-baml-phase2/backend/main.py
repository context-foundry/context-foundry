"""
FastAPI application for task manager backend.
Provides RESTful API endpoints for CRUD operations on tasks.
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import List

from models import Task, TaskCreate, TaskUpdate
import database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    database.init_db()
    yield


app = FastAPI(
    title="Task Manager API",
    description="RESTful API for managing tasks",
    version="1.0.0",
    lifespan=lifespan,
)

# CRITICAL: CORS middleware to allow frontend requests from Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", status_code=status.HTTP_200_OK)
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "task-manager-api"}


@app.get("/tasks", response_model=List[Task], status_code=status.HTTP_200_OK)
async def get_tasks():
    """Retrieve all tasks."""
    tasks = database.get_all_tasks()
    return tasks


@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task(task_data: TaskCreate):
    """Create a new task."""
    task = database.create_task(
        title=task_data.title, description=task_data.description
    )
    return task


@app.put("/tasks/{task_id}", response_model=Task, status_code=status.HTTP_200_OK)
async def update_task(task_id: int, task_data: TaskUpdate):
    """Update an existing task."""
    task = database.update_task(
        task_id=task_id,
        title=task_data.title,
        description=task_data.description,
        completed=task_data.completed,
    )

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found",
        )

    return task


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int):
    """Delete a task."""
    deleted = database.delete_task(task_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found",
        )

    return None
