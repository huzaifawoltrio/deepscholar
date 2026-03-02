"""LangChain tool that searches Google via SerpAPI for supplementary web sources."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_RESULTS = 5


@tool
def search_web(query: str) -> list[dict[str, Any]]:
    """Search Google for supplementary web sources related to the query.

    Returns a list of dicts with keys:
        title, authors, date, publication, abstract, url
    """
    try:
        from serpapi import GoogleSearch

        params = {
            "engine": "google",
            "q": query,
            "num": MAX_RESULTS,
            "api_key": settings.SERP_API_KEY,
        }
        search = GoogleSearch(params)
        data = search.get_dict()

        results: list[dict[str, Any]] = []
        for item in data.get("organic_results", [])[:MAX_RESULTS]:
            results.append(
                {
                    "title": item.get("title", ""),
                    "authors": [],
                    "date": item.get("date", "N/A"),
                    "publication": _extract_domain(item.get("link", "")),
                    "abstract": item.get("snippet", ""),
                    "url": item.get("link", ""),
                }
            )
        logger.info("Web search returned %d results for: %s", len(results), query)
        return results
    except Exception as exc:
        logger.error("Web search failed: %s", exc)
        return []


def _extract_domain(url: str) -> str:
    """Extract a clean domain name from a URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
        return domain or "Web"
    except Exception:
        return "Web"
