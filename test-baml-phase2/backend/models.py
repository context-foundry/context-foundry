"""
Pydantic models for request/response validation.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class TaskBase(BaseModel):
    """Base task model with common fields."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)


class TaskCreate(TaskBase):
    """Model for creating a new task."""

    pass


class TaskUpdate(BaseModel):
    """Model for updating an existing task (all fields optional)."""

    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    completed: Optional[bool] = None


class Task(TaskBase):
    """Complete task model with all database fields."""

    id: int
    completed: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
