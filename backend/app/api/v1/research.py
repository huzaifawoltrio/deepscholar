"""Research endpoint — accepts a query and returns a synthesized academic answer."""

import logging
import traceback
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api import deps
from app.models.user import User
from app.schemas.research import ResearchRequest, ResearchResponse
from app.services.research_agent import run_research

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    response_model=ResearchResponse,
    summary="Submit a research query and receive a synthesized academic answer",
)
async def research(
    *,
    body: ResearchRequest,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Accept a research query, orchestrate a multi-source academic search via
    the LangChain agent, and return a structured response with inline
    citations and a references sidebar list.
    """
    try:
        result = await run_research(body.query)
        return result
    except Exception as exc:
        logger.error(
            "Research endpoint failed for query '%s': %s\n%s",
            body.query, exc, traceback.format_exc(),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Research processing failed: {str(exc)}",
        )
