"""Pydantic schemas for chat sessions and messages."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------
class MessageOut(BaseModel):
    """A single chat message returned to the frontend."""
    id: int
    role: str
    content: str
    references: Optional[list] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------
class SessionCreate(BaseModel):
    """Payload to create a new chat session (title is optional)."""
    title: Optional[str] = None


class SessionOut(BaseModel):
    """Chat session summary returned in listings."""
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionDetail(SessionOut):
    """Chat session with full message history."""
    messages: list[MessageOut] = []


# ---------------------------------------------------------------------------
# Research request (extended to support sessions)
# ---------------------------------------------------------------------------
class SessionResearchRequest(BaseModel):
    """Research query tied to a session."""
    query: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[int] = None
