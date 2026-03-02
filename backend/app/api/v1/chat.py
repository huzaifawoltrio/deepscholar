"""Chat session endpoints — CRUD for sessions and messages, plus session-aware research."""

import logging
import traceback
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.crud import crud_chat
from app.models.user import User
from app.schemas.chat import (
    SessionCreate,
    SessionOut,
    SessionDetail,
    SessionResearchRequest,
    MessageOut,
)
from app.schemas.research import ResearchResponse
from app.services.research_agent import run_research

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------
@router.get("", response_model=list[SessionOut], summary="List all chat sessions")
async def list_sessions(
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    return await crud_chat.list_sessions(db, user_id=current_user.id)


@router.post("", response_model=SessionOut, status_code=201, summary="Create a new chat session")
async def create_session(
    body: SessionCreate = SessionCreate(),
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    title = body.title or "New Research"
    return await crud_chat.create_session(db, user_id=current_user.id, title=title)


@router.get("/{session_id}", response_model=SessionDetail, summary="Get session with messages")
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    session = await crud_chat.get_session(db, session_id=session_id, user_id=current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/{session_id}", status_code=204, summary="Delete a chat session")
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> None:
    deleted = await crud_chat.delete_session(db, session_id=session_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")


@router.patch("/{session_id}", response_model=SessionOut, summary="Rename a chat session")
async def rename_session(
    session_id: int,
    body: SessionCreate,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    session = await crud_chat.update_session_title(
        db, session_id=session_id, user_id=current_user.id, title=body.title or "New Research"
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ---------------------------------------------------------------------------
# Session-aware research
# ---------------------------------------------------------------------------
@router.post(
    "/{session_id}/research",
    response_model=ResearchResponse,
    summary="Send a research query within a session",
)
async def session_research(
    session_id: int,
    body: SessionResearchRequest,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    # Verify session ownership
    session = await crud_chat.get_session(db, session_id=session_id, user_id=current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Store the user message
    await crud_chat.add_message(db, session_id=session_id, role="user", content=body.query)

    # Build chat history for AI context (last 20 messages)
    history_msgs = await crud_chat.get_messages(db, session_id=session_id, limit=20)
    chat_history = [
        {"role": m.role, "content": m.content}
        for m in history_msgs
        if m.content != body.query or m.role != "user"  # exclude the just-added message
    ]

    # Auto-title on first user message
    if session.title == "New Research":
        short_title = body.query[:80].strip()
        if len(body.query) > 80:
            short_title += "..."
        await crud_chat.update_session_title(
            db, session_id=session_id, user_id=current_user.id, title=short_title
        )

    try:
        result = await run_research(body.query, chat_history=chat_history)

        # Store the assistant response
        await crud_chat.add_message(
            db,
            session_id=session_id,
            role="assistant",
            content=result["response"],
            references=result.get("references"),
        )

        return result
    except Exception as exc:
        logger.error(
            "Session research failed for query '%s': %s\n%s",
            body.query, exc, traceback.format_exc(),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Research processing failed: {str(exc)}",
        )
