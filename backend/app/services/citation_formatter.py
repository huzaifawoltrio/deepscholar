"""Utility to map raw source dicts to the frontend Reference schema."""

from __future__ import annotations

from typing import Any

from app.schemas.research import ReferenceOut


def format_references(sources: list[dict[str, Any]]) -> list[ReferenceOut]:
    """Convert raw source dicts into the frontend-expected ReferenceOut list.

    Each source is assigned a sequential `ref_N` id.
    """
    references: list[ReferenceOut] = []
    seen_titles: set[str] = set()

    for source in sources:
        title = source.get("title", "").strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)

        ref = ReferenceOut(
            id=f"ref_{len(references) + 1}",
            title=title,
            authors=source.get("authors", []) or ["Unknown"],
            date=source.get("date", "N/A"),
            publication=source.get("publication", "Unknown"),
            impactFactor=source.get("impactFactor"),
        )
        references.append(ref)

    return references


def build_context_block(sources: list[dict[str, Any]]) -> str:
    """Build a numbered context string for the LLM synthesis prompt.

    The number corresponds to the citation index [N] the LLM should use.
    """
    if not sources:
        return "No sources available."

    lines: list[str] = []
    seen_titles: set[str] = set()
    idx = 0

    for source in sources:
        title = source.get("title", "").strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        idx += 1

        abstract = source.get("abstract", "").strip() or "No abstract available."
        authors = ", ".join(source.get("authors", []) or ["Unknown"])
        date = source.get("date", "N/A")
        publication = source.get("publication", "Unknown")

        lines.append(
            f"[{idx}] {title}\n"
            f"    Authors: {authors}\n"
            f"    Date: {date} | Publication: {publication}\n"
            f"    Content: {abstract}\n"
        )

    return "\n".join(lines)
