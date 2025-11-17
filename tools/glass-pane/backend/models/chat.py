"""
Chat data models for API validation and serialization.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    """Request body for sending a chat message."""

    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    session_id: Optional[str] = Field(
        None, description="Existing session ID or None for new session"
    )
    message: str = Field(..., description="User message content", min_length=1)
    model: str = Field("sonnet", description="Claude model: sonnet, opus, haiku")
    plan_mode: bool = Field(False, description="Enable plan mode")
    bypass_permissions: bool = Field(False, description="Bypass permission checks")


class ChatMessageResponse(BaseModel):
    """Response model for a chat message."""

    id: int
    session_id: str
    role: str
    content: str
    timestamp: str
    tokens_used: Optional[int] = None


class ChatSessionResponse(BaseModel):
    """Response model for a chat session."""

    id: str
    created_at: str
    last_activity: str
    model: str
    plan_mode: bool
    bypass_permissions: bool
    title: Optional[str]
    message_count: int


class ChatSessionListResponse(BaseModel):
    """Response for listing chat sessions."""

    sessions: List[ChatSessionResponse]
    total: int
    limit: int
    offset: int


class ChatHistoryResponse(BaseModel):
    """Response for getting session history."""

    session: ChatSessionResponse
    messages: List[ChatMessageResponse]


class ChatStreamEvent(BaseModel):
    """SSE event for chat streaming."""

    type: str = Field(..., description="Event type: delta, complete, error")
    text: Optional[str] = Field(None, description="Text content for delta/complete")
    message: Optional[str] = Field(None, description="Error message if type=error")
    session_id: Optional[str] = Field(None, description="Session ID")


class CreateSessionRequest(BaseModel):
    """Request to create a new chat session."""

    model: str = Field("sonnet", description="Claude model")
    plan_mode: bool = Field(False, description="Enable plan mode")
    bypass_permissions: bool = Field(False, description="Bypass permissions")
    title: Optional[str] = Field(None, description="Session title")


class UpdateSessionRequest(BaseModel):
    """Request to update session settings."""

    model: Optional[str] = None
    plan_mode: Optional[bool] = None
    bypass_permissions: Optional[bool] = None
    title: Optional[str] = None


class CLIStatusResponse(BaseModel):
    """Response for CLI availability check."""

    available: bool
    path: Optional[str] = None
    version: Optional[str] = None
    error: Optional[str] = None
