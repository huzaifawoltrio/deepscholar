"""LangChain tool that searches Google Scholar via SerpAPI."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_RESULTS = 5


@tool
def search_scholar(query: str) -> list[dict[str, Any]]:
    """Search Google Scholar for peer-reviewed academic papers.

    Returns a list of dicts with keys:
        title, authors, date, publication, abstract, url
    """
    try:
        from serpapi import GoogleSearch

        params = {
            "engine": "google_scholar",
            "q": query,
            "num": MAX_RESULTS,
            "api_key": settings.SERP_API_KEY,
        }
        search = GoogleSearch(params)
        data = search.get_dict()

        results: list[dict[str, Any]] = []
        for item in data.get("organic_results", [])[:MAX_RESULTS]:
            pub_info = item.get("publication_info", {})
            results.append(
                {
                    "title": item.get("title", ""),
                    "authors": _parse_authors(pub_info.get("summary", "")),
                    "date": _extract_year(pub_info.get("summary", "")),
                    "publication": pub_info.get("summary", "").split("-")[-1].strip() if "-" in pub_info.get("summary", "") else "Academic Journal",
                    "abstract": item.get("snippet", ""),
                    "url": item.get("link", ""),
                }
            )
        logger.info("Google Scholar returned %d results for: %s", len(results), query)
        return results
    except Exception as exc:
        logger.error("Google Scholar search failed: %s", exc)
        return []


def _parse_authors(summary: str) -> list[str]:
    """Extract author names from the publication_info summary string."""
    if "-" not in summary:
        return ["Unknown"]
    author_part = summary.split("-")[0].strip()
    authors = [a.strip() for a in author_part.split(",") if a.strip()]
    return authors[:5] if authors else ["Unknown"]


def _extract_year(summary: str) -> str:
    """Try to extract a year from the summary string."""
    import re
    match = re.search(r"(\d{4})", summary)
    return match.group(1) if match else "N/A"
