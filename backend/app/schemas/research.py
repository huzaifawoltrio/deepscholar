from pydantic import BaseModel, Field
from typing import Optional


class ResearchRequest(BaseModel):
    """Incoming research query from the frontend."""
    query: str = Field(..., min_length=1, max_length=2000, description="The research question")


class ReferenceOut(BaseModel):
    """Single reference matching the frontend Reference interface."""
    id: str
    title: str
    authors: list[str]
    date: str
    publication: str
    url: Optional[str] = None
    impactFactor: Optional[float] = None


class ResearchResponse(BaseModel):
    """Response schema matching the frontend expected contract."""
    response: str
    references: list[ReferenceOut]
