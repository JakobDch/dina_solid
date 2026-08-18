"""
Chat Sessions Router

Persists chat sessions and their messages so a conversation can be restored
after a page reload and so follow-up questions keep their context.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from ..db import get_session
from ..models import (
    ChatSession,
    ChatSessionMessage,
    ChatSessionRead,
    CreateChatSessionRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["Chat Sessions"])


async def create_chat_session(
    workspace_id: str,
    initial_query: str,
    selected_models: List[str],
    model_info_blocks: str,
    model_check_hints: str,
    db_session,
    sparql_query: Optional[str] = None,
    sparql_results: Optional[Dict] = None,
    sparql_variables: Optional[List[str]] = None,
) -> ChatSession:
    """Create a new chat session after a successful query."""
    session = ChatSession(
        workspace_id=workspace_id,
        initial_query=initial_query,
        selected_models=selected_models,
        model_info_blocks=model_info_blocks,
        model_check_hints=model_check_hints,
        last_sparql_query=sparql_query,
        last_sparql_results=sparql_results,
        last_sparql_variables=sparql_variables,
    )

    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    logger.info(f"Created chat session {session.id} for workspace {workspace_id}")
    return session


async def add_message_to_session(
    session_id: str,
    message: str,
    is_user_message: bool,
    sparql_query: Optional[str] = None,
    sparql_results: Optional[Dict] = None,
    step_id: Optional[str] = None,
    db_session=None,
) -> None:
    """Append a message to an existing chat session."""
    db_session.add(
        ChatSessionMessage(
            session_id=session_id,
            message=message,
            is_user_message=is_user_message,
            sparql_query=sparql_query,
            sparql_results=sparql_results,
            step_id=step_id,
        )
    )

    session = db_session.get(ChatSession, session_id)
    if session:
        session.last_activity = datetime.now(timezone.utc)

    db_session.commit()


async def get_recent_session_messages(
    session_id: str, limit: int = 10, db_session=None
) -> List[ChatSessionMessage]:
    """Return the most recent messages of a session in chronological order."""
    statement = (
        select(ChatSessionMessage)
        .where(ChatSessionMessage.session_id == session_id)
        .order_by(ChatSessionMessage.timestamp.desc())
        .limit(limit)
    )
    return list(reversed(db_session.exec(statement).all()))


def _to_read_model(session: ChatSession) -> ChatSessionRead:
    return ChatSessionRead(
        id=session.id,
        workspace_id=session.workspace_id,
        created_at=session.created_at,
        last_activity=session.last_activity,
        initial_query=session.initial_query,
        selected_models=session.selected_models,
        is_active=session.is_active,
    )


@router.post("/sessions", summary="Create a chat session")
async def create_session_endpoint(
    request_data: CreateChatSessionRequest,
    db: Session = Depends(get_session),
) -> ChatSessionRead:
    """Create a chat session for a workspace."""
    try:
        session = await create_chat_session(
            workspace_id=request_data.workspace_id,
            initial_query=request_data.initial_query,
            selected_models=request_data.selected_models,
            model_info_blocks=request_data.model_info_blocks,
            model_check_hints=request_data.model_check_hints,
            db_session=db,
            sparql_query=request_data.sparql_query,
            sparql_results=request_data.sparql_results,
            sparql_variables=request_data.sparql_variables,
        )
        return _to_read_model(session)
    except Exception as exc:
        logger.error(f"Error creating chat session: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {exc}",
        )


@router.get("/sessions/{workspace_id}", summary="List active sessions of a workspace")
async def get_workspace_sessions(
    workspace_id: str,
    db: Session = Depends(get_session),
) -> List[ChatSessionRead]:
    """Return every active chat session of a workspace, most recent first."""
    try:
        statement = (
            select(ChatSession)
            .where(ChatSession.workspace_id == workspace_id, ChatSession.is_active == True)  # noqa: E712
            .order_by(ChatSession.last_activity.desc())
        )
        return [_to_read_model(session) for session in db.exec(statement).all()]
    except Exception as exc:
        logger.error(f"Error retrieving workspace sessions: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve sessions: {exc}",
        )


@router.delete("/sessions/{session_id}", summary="Deactivate a chat session")
async def end_session(session_id: str, db: Session = Depends(get_session)):
    """Mark a chat session as inactive."""
    session = db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    session.is_active = False
    db.add(session)
    db.commit()

    logger.info(f"Ended chat session {session_id}")
    return {"message": "Session ended successfully", "session_id": session_id}


@router.get("/sessions/{session_id}/messages", summary="Read the messages of a session")
async def get_session_messages(
    session_id: str,
    limit: int = 50,
    db: Session = Depends(get_session),
):
    """Return a session's messages so the frontend can restore the history."""
    session = db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    messages = await get_recent_session_messages(session_id, limit=limit, db_session=db)

    return {
        "session_id": session_id,
        "messages": [
            {
                "id": message.id,
                "message": message.message,
                "is_user_message": message.is_user_message,
                "timestamp": message.timestamp.isoformat(),
                "sparql_query": message.sparql_query,
                "sparql_results": message.sparql_results,
                "step_id": message.step_id,
            }
            for message in messages
        ],
    }
