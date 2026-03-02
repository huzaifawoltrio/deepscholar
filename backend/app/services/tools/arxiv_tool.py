"""LangChain tool that searches arXiv for academic papers."""

from __future__ import annotations

import logging
from typing import Any

import arxiv
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

MAX_RESULTS = 5


@tool
def search_arxiv(query: str) -> list[dict[str, Any]]:
    """Search arXiv for academic papers related to the query.
    IMPORTANT: The query MUST be a short, concise set of keywords (e.g. 'artificial intelligence medicine'), NOT a full sentence.

    Returns a list of dicts with keys:
        title, authors, date, publication, abstract, url
    """
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=MAX_RESULTS,
            sort_by=arxiv.SortCriterion.Relevance,
        )

        results: list[dict[str, Any]] = []
        for paper in client.results(search):
            results.append(
                {
                    "title": paper.title,
                    "authors": [a.name for a in paper.authors[:5]],
                    "date": paper.published.strftime("%Y.%m.%d"),
                    "publication": "arXiv",
                    "abstract": paper.summary[:500],
                    "url": paper.entry_id,
                }
            )
        logger.info("arXiv returned %d results for: %s", len(results), query)
        return results
    except Exception as exc:
        logger.error("arXiv search failed: %s", exc)
        return []
