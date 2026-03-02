"""LangChain agent that orchestrates multi-source academic research."""

from __future__ import annotations

import json
import logging
import traceback
from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from app.core.config import settings
from app.services.tools.arxiv_tool import search_arxiv
from app.services.tools.scholar_tool import search_scholar
from app.services.tools.serp_tool import search_web
from app.services import vectorstore
from app.services.citation_formatter import format_references, build_context_block
from app.schemas.research import ReferenceOut

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent System Prompt
# ---------------------------------------------------------------------------
AGENT_SYSTEM_PROMPT = """\
You are a research assistant. Your job is to gather sources for the user's \
academic query. Use the available tools to search for relevant papers and web \
sources. Call each tool at least once. Collect as many relevant results as \
possible. When you have enough sources (aim for at least 5-10 diverse results), \
stop and return all gathered sources as a single JSON array.

IMPORTANT: Return ONLY a valid JSON array of source objects at the very end. \
Each object must have: title, authors, date, publication, abstract, url.
Do NOT include any other text outside the JSON array in your final response.\
"""

# ---------------------------------------------------------------------------
# Synthesis System Prompt
# ---------------------------------------------------------------------------
SYNTHESIS_SYSTEM_PROMPT = """\
You are DeepScholar, an expert academic research assistant. You write in a \
formal academic tone. You have been provided with a set of numbered research \
sources retrieved from scholarly databases.

Your task:
1. Synthesize a comprehensive, well-structured academic response to the user's \
   question using ONLY the provided sources.
2. Reference sources using inline citation markers in the format [N](URL) where \
   N is the source number and URL is the source's URL from the provided context. \
   For example: "Recent studies show that...[1](https://arxiv.org/abs/1234)."
3. Do NOT invent or fabricate any references. ONLY cite sources from the \
   provided context below.
4. Structure your answer with clear paragraphs. Use markdown formatting where \
   appropriate (bold, headers, lists).
5. End with a brief concluding paragraph summarizing key findings.
6. If the provided sources do not adequately address the query, state this \
   clearly rather than speculating.

--- PROVIDED SOURCES ---
{context}
--- END SOURCES ---
"""


def _get_llm(temperature: float = 0.0) -> ChatGoogleGenerativeAI:
    """Create a Gemini LLM instance."""
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=temperature,
    )


def _parse_sources_from_agent(output: str) -> list[dict[str, Any]]:
    """Try to extract a JSON array of source objects from the agent output."""
    text = output.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Try to find JSON array
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning("Could not parse sources JSON from agent output")
    return []


async def run_research(
    query: str,
    chat_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Run the full research pipeline for a user query.

    Args:
        query: The user's research question.
        chat_history: Optional list of previous messages [{"role": ..., "content": ...}]
                      to give the AI conversational memory.

    Returns a dict with 'response' (str) and 'references' (list[ReferenceOut]).
    """
    logger.info("Starting research for query: %s", query)

    # ------------------------------------------------------------------
    # Step 1: Use LangGraph ReAct agent to gather sources from tools
    # ------------------------------------------------------------------
    llm = _get_llm(temperature=0.0)
    tools = [search_arxiv, search_scholar, search_web]

    # Try to create the agent (handle different langgraph versions)
    try:
        try:
            agent = create_react_agent(
                model=llm,
                tools=tools,
                prompt=AGENT_SYSTEM_PROMPT,
            )
        except TypeError:
            # Older langgraph versions use state_modifier instead of prompt
            agent = create_react_agent(
                model=llm,
                tools=tools,
                state_modifier=AGENT_SYSTEM_PROMPT,
            )

        agent_result = await agent.ainvoke(
            {"messages": [HumanMessage(content=query)]}
        )

        # Extract the final AI message content
        raw_output = ""
        for msg in reversed(agent_result.get("messages", [])):
            # Check content exists and tool_calls is empty/absent (not just missing)
            if hasattr(msg, "content") and msg.content and not getattr(msg, "tool_calls", None):
                raw_output = msg.content if isinstance(msg.content, str) else str(msg.content)
                break

        logger.info("Agent raw output length: %d", len(raw_output))

        # Parse the gathered sources
        gathered_sources = _parse_sources_from_agent(raw_output)
        logger.info("Agent gathered %d sources", len(gathered_sources))
    except Exception as exc:
        logger.error("Agent execution failed: %s\n%s", exc, traceback.format_exc())
        gathered_sources = []

    # If agent didn't return parseable JSON, try to call tools directly as fallback
    if not gathered_sources:
        logger.warning("Agent returned no parseable sources, falling back to direct tool calls")
        gathered_sources = []
        for tool_fn in [search_arxiv, search_scholar, search_web]:
            try:
                results = tool_fn.invoke(query)
                if isinstance(results, list):
                    gathered_sources.extend(results)
                    logger.info("Fallback tool %s returned %d results", tool_fn.name, len(results))
            except Exception as exc:
                logger.error("Fallback tool call failed: %s\n%s", exc, traceback.format_exc())

    if not gathered_sources:
        return {
            "response": "I was unable to find relevant academic sources for your query. Please try rephrasing your question or using more specific academic terms.",
            "references": [],
        }

    # ------------------------------------------------------------------
    # Step 2: Use freshly gathered sources directly for synthesis
    # ------------------------------------------------------------------
    # NOTE: We skip Pinecone retrieval because the shared global index
    # mixes results from all past queries, returning stale/irrelevant
    # sources. The freshly gathered sources are already query-specific
    # and most relevant.
    sources_for_synthesis = gathered_sources

    # Optionally store in Pinecone for long-term knowledge base (fire-and-forget)
    try:
        vectorstore.embed_and_store(gathered_sources)
    except Exception as exc:
        logger.warning("Pinecone storage failed (non-blocking): %s", exc)

    # ------------------------------------------------------------------
    # Step 3: Build context and synthesize academic response
    # ------------------------------------------------------------------
    context_block = build_context_block(sources_for_synthesis)
    references = format_references(sources_for_synthesis)

    synthesis_llm = _get_llm(temperature=0.3)
    messages = [
        SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT.format(context=context_block)),
    ]

    # Inject prior conversation history so the AI remembers the chat
    if chat_history:
        for hist_msg in chat_history:
            if hist_msg["role"] == "user":
                messages.append(HumanMessage(content=hist_msg["content"]))
            elif hist_msg["role"] == "assistant":
                messages.append(AIMessage(content=hist_msg["content"]))

    messages.append(HumanMessage(content=query))

    try:
        synthesis_response = await synthesis_llm.ainvoke(messages)
        response_text = synthesis_response.content
    except Exception as exc:
        logger.error("Synthesis LLM failed: %s\n%s", exc, traceback.format_exc())
        # Return a basic summary from the gathered sources instead of crashing
        response_text = (
            "⚠️ The AI synthesis model is temporarily unavailable (quota exceeded). "
            "However, I found the following sources for your query. "
            "Please review the references panel for details.\n\n"
        )
        for i, ref in enumerate(references, 1):
            response_text += f"**[{i}]** {ref.title} — {', '.join(ref.authors)} ({ref.date})\n\n"

    logger.info(
        "Research complete: %d chars response, %d references",
        len(response_text),
        len(references),
    )

    return {
        "response": response_text,
        "references": [ref.model_dump() for ref in references],
    }

