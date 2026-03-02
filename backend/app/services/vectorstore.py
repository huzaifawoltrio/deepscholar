"""Pinecone vector store for embedding and retrieving research sources (RAG)."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from pinecone import Pinecone, ServerlessSpec
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = settings.EMBEDDING_MODEL
EMBEDDING_DIMENSION = 768  # Google text-embedding-004 dimension
INDEX_METRIC = "cosine"


def _get_pinecone_index():
    """Initialise Pinecone client and return the index, creating if needed."""
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    index_name = settings.PINECONE_INDEX_NAME

    existing = [idx.name for idx in pc.list_indexes()]
    if index_name not in existing:
        logger.info("Creating Pinecone index '%s'", index_name)
        pc.create_index(
            name=index_name,
            dimension=EMBEDDING_DIMENSION,
            metric=INDEX_METRIC,
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )

    return pc.Index(index_name)


def _get_embeddings() -> GoogleGenerativeAIEmbeddings:
    """Return the Google Generative AI embeddings model."""
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
    )


def _source_id(source: dict) -> str:
    """Generate a deterministic ID for a source to avoid duplicates."""
    raw = f"{source.get('title', '')}-{source.get('url', '')}".encode()
    return hashlib.md5(raw).hexdigest()


def embed_and_store(sources: list[dict[str, Any]]) -> None:
    """Embed source abstracts/snippets and upsert into Pinecone.

    Each source dict should have: title, authors, date, publication, abstract, url.
    """
    if not sources:
        return

    index = _get_pinecone_index()
    embeddings = _get_embeddings()

    texts = [s.get("abstract", "") or s.get("title", "") for s in sources]
    vectors = embeddings.embed_documents(texts)

    upsert_data = []
    for source, vec in zip(sources, vectors):
        doc_id = _source_id(source)
        metadata = {
            "title": source.get("title", ""),
            "authors": ", ".join(source.get("authors", [])),
            "date": source.get("date", ""),
            "publication": source.get("publication", ""),
            "abstract": (source.get("abstract", "") or "")[:1000],
            "url": source.get("url", ""),
        }
        upsert_data.append((doc_id, vec, metadata))

    index.upsert(vectors=upsert_data)
    logger.info("Upserted %d vectors into Pinecone", len(upsert_data))


def retrieve(query: str, top_k: int = 10) -> list[dict[str, Any]]:
    """Retrieve the most semantically relevant sources for a query.

    Returns a list of metadata dicts ranked by similarity.
    """
    index = _get_pinecone_index()
    embeddings = _get_embeddings()

    query_vec = embeddings.embed_query(query)
    results = index.query(vector=query_vec, top_k=top_k, include_metadata=True)

    retrieved: list[dict[str, Any]] = []
    for match in results.get("matches", []):
        meta = match.get("metadata", {})
        retrieved.append(
            {
                "title": meta.get("title", ""),
                "authors": [a.strip() for a in meta.get("authors", "").split(",") if a.strip()],
                "date": meta.get("date", ""),
                "publication": meta.get("publication", ""),
                "abstract": meta.get("abstract", ""),
                "url": meta.get("url", ""),
                "score": match.get("score", 0.0),
            }
        )
    logger.info("Retrieved %d results from Pinecone for: %s", len(retrieved), query)
    return retrieved
