"""
Chat API endpoints for Forge interface.

Provides endpoints for managing chat sessions, sending messages,
and streaming responses from Claude CLI.
"""

import logging
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from models.chat import (
    ChatRequest,
    ChatSessionResponse,
    ChatSessionListResponse,
    ChatHistoryResponse,
    ChatMessageResponse,
    CreateSessionRequest,
    UpdateSessionRequest,
    CLIStatusResponse,
)
from services.chat_service import ChatService
from services.claude_cli import ClaudeCLIService, ClaudeMessage, ClaudeConfig
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Initialize services
chat_service = ChatService(settings.expanded_db_path)
claude_cli = ClaudeCLIService()


@router.post("/send")
async def send_message(request: ChatRequest):
    """
    Send a message to Claude and stream the response.

    Returns SSE stream with delta events for real-time updates.
    """
    try:
        # Get or create session
        if request.session_id:
            session = chat_service.get_session(request.session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
        else:
            # Create new session
            session = chat_service.create_session(
                model=request.model,
                plan_mode=request.plan_mode,
                bypass_permissions=request.bypass_permissions,
                working_directory=request.working_directory,
            )

        # Save user message
        chat_service.add_message(
            session_id=session.id, role="user", content=request.message
        )

        # Get conversation history
        messages = chat_service.get_session_messages(session.id)

        # Convert to ClaudeMessage format
        claude_messages = [
            ClaudeMessage(role=msg.role, content=msg.content) for msg in messages
        ]

        # Prepend system prompt if available
        if claude_cli.system_prompt:
            claude_messages.insert(
                0, ClaudeMessage(role="system", content=claude_cli.system_prompt)
            )

        # Configure CLI
        config = ClaudeConfig(
            model=request.model,
            plan_mode=request.plan_mode,
            bypass_permissions=request.bypass_permissions,
            timeout=120,  # 2 minute timeout for chat
        )

        # Determine working directory (request override or session default)
        working_directory = request.working_directory or session.working_directory

        # Stream response
        async def event_generator():
            """Generate SSE events from Claude CLI stream."""
            accumulated_response = []

            try:
                async for event in claude_cli.chat_stream(
                    claude_messages, config, cwd=working_directory
                ):
                    event_type = event.get("type")

                    if event_type == "delta":
                        # Stream text delta
                        text = event.get("text", "")
                        accumulated_response.append(text)
                        yield {
                            "event": "delta",
                            "data": {
                                "type": "delta",
                                "text": text,
                                "session_id": session.id,
                            },
                        }

                    elif event_type == "complete":
                        # Save assistant response to database
                        complete_text = "".join(accumulated_response)
                        chat_service.add_message(
                            session_id=session.id,
                            role="assistant",
                            content=complete_text,
                        )

                        yield {
                            "event": "complete",
                            "data": {
                                "type": "complete",
                                "text": complete_text,
                                "session_id": session.id,
                            },
                        }

                    elif event_type == "error":
                        # Stream error
                        error_msg = event.get("message", "Unknown error")
                        logger.error(f"Claude CLI error: {error_msg}")
                        yield {
                            "event": "error",
                            "data": {
                                "type": "error",
                                "message": error_msg,
                                "session_id": session.id,
                            },
                        }

            except Exception as e:
                logger.error(f"Error in chat stream: {e}", exc_info=True)
                yield {
                    "event": "error",
                    "data": {
                        "type": "error",
                        "message": str(e),
                        "session_id": session.id,
                    },
                }

        return EventSourceResponse(event_generator())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in send_message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== Session Management ==========


@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(request: CreateSessionRequest):
    """Create a new chat session."""
    try:
        session = chat_service.create_session(
            model=request.model,
            plan_mode=request.plan_mode,
            bypass_permissions=request.bypass_permissions,
            title=request.title,
            working_directory=request.working_directory,
        )

        return ChatSessionResponse(
            id=session.id,
            created_at=session.created_at,
            last_activity=session.last_activity,
            model=session.model,
            plan_mode=session.plan_mode,
            bypass_permissions=session.bypass_permissions,
            title=session.title,
            message_count=session.message_count,
            working_directory=session.working_directory,
        )
    except Exception as e:
        logger.error(f"Error creating session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(limit: int = 50, offset: int = 0):
    """List all chat sessions."""
    try:
        sessions, total = chat_service.list_sessions(limit=limit, offset=offset)

        return ChatSessionListResponse(
            sessions=[
                ChatSessionResponse(
                    id=s.id,
                    created_at=s.created_at,
                    last_activity=s.last_activity,
                    model=s.model,
                    plan_mode=s.plan_mode,
                    bypass_permissions=s.bypass_permissions,
                    title=s.title,
                    message_count=s.message_count,
                    working_directory=s.working_directory,
                )
                for s in sessions
            ],
            total=total,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error(f"Error listing sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}", response_model=ChatHistoryResponse)
async def get_session_history(session_id: str):
    """Get session details and message history."""
    try:
        session = chat_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        messages = chat_service.get_session_messages(session_id)

        return ChatHistoryResponse(
            session=ChatSessionResponse(
                id=session.id,
                created_at=session.created_at,
                last_activity=session.last_activity,
                model=session.model,
                plan_mode=session.plan_mode,
                bypass_permissions=session.bypass_permissions,
                title=session.title,
                message_count=session.message_count,
                working_directory=session.working_directory,
            ),
            messages=[
                ChatMessageResponse(
                    id=m.id,
                    session_id=m.session_id,
                    role=m.role,
                    content=m.content,
                    timestamp=m.timestamp,
                    tokens_used=m.tokens_used,
                )
                for m in messages
            ],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_session(session_id: str, request: UpdateSessionRequest):
    """Update session settings."""
    try:
        success = chat_service.update_session(
            session_id=session_id,
            model=request.model,
            plan_mode=request.plan_mode,
            bypass_permissions=request.bypass_permissions,
            title=request.title,
            working_directory=request.working_directory,
        )

        if not success:
            raise HTTPException(status_code=404, detail="Session not found")

        session = chat_service.get_session(session_id)
        return ChatSessionResponse(
            id=session.id,
            created_at=session.created_at,
            last_activity=session.last_activity,
            model=session.model,
            plan_mode=session.plan_mode,
            bypass_permissions=session.bypass_permissions,
            title=session.title,
            message_count=session.message_count,
            working_directory=session.working_directory,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session and all its messages."""
    try:
        success = chat_service.delete_session(session_id)

        if not success:
            raise HTTPException(status_code=404, detail="Session not found")

        return {"success": True, "message": f"Session {session_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}/messages")
async def clear_session_messages(session_id: str):
    """Clear all messages from a session."""
    try:
        count = chat_service.clear_session_messages(session_id)

        return {"success": True, "message": f"Cleared {count} messages", "count": count}
    except Exception as e:
        logger.error(f"Error clearing messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ========== CLI Status ==========


@router.get("/cli-status", response_model=CLIStatusResponse)
async def get_cli_status():
    """Check Claude CLI availability and version."""
    try:
        status = await claude_cli.check_availability()
        return CLIStatusResponse(**status)
    except Exception as e:
        logger.error(f"Error checking CLI status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
