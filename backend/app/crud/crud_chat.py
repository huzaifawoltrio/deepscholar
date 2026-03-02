"""CRUD helpers for chat sessions and messages."""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Optional, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import ChatSession, ChatMessage


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
async def create_session(
    db: AsyncSession, *, user_id: int, title: str = "New Research"
) -> ChatSession:
    session = ChatSession(user_id=user_id, title=title)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(
    db: AsyncSession, *, session_id: int, user_id: int
) -> Optional[ChatSession]:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id, ChatSession.user_id == user_id)
        .options(selectinload(ChatSession.messages))
    )
    return result.scalars().first()


async def list_sessions(
    db: AsyncSession, *, user_id: int, skip: int = 0, limit: int = 50
) -> list[ChatSession]:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(result.scalars().all())


async def delete_session(
    db: AsyncSession, *, session_id: int, user_id: int
) -> bool:
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == user_id
        )
    )
    session = result.scalars().first()
    if not session:
        return False
    await db.delete(session)
    await db.commit()
    return True


async def update_session_title(
    db: AsyncSession, *, session_id: int, user_id: int, title: str
) -> Optional[ChatSession]:
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == user_id
        )
    )
    session = result.scalars().first()
    if not session:
        return None
    session.title = title
    session.updated_at = datetime.now(UTC)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def touch_session(db: AsyncSession, *, session_id: int) -> None:
    """Update the updated_at timestamp (called when a new message is added)."""
    await db.execute(
        update(ChatSession)
        .where(ChatSession.id == session_id)
        .values(updated_at=datetime.now(UTC))
    )


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
async def add_message(
    db: AsyncSession,
    *,
    session_id: int,
    role: str,
    content: str,
    references: Optional[list[dict[str, Any]]] = None,
) -> ChatMessage:
    msg = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        references=references,
    )
    db.add(msg)
    await touch_session(db, session_id=session_id)
    await db.commit()
    await db.refresh(msg)
    return msg


async def get_messages(
    db: AsyncSession, *, session_id: int, limit: int = 100
) -> list[ChatMessage]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())
