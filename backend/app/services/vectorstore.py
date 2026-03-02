"""Pinecone vector store for embedding and retrieving research sources (RAG)."""

from __future__ import annotations

import hashlib
import logging
import time
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


def embed_and_store(sources: list[dict[str, Any]], namespace: str = "") -> None:
    """Embed source abstracts/snippets and upsert into Pinecone.

    Each source dict should have: title, authors, date, publication, abstract, url.
    If namespace is provided, vectors are stored in that specific namespace.
    """
    if not sources:
        return

    index = _get_pinecone_index()
    embeddings = _get_embeddings()

    # Batch process to avoid hitting Google GenAI Free Tier rate limits (100 RPM)
    BATCH_SIZE = 50
    upsert_data = []

    for i in range(0, len(sources), BATCH_SIZE):
        batch_sources = sources[i:i + BATCH_SIZE]
        texts = [s.get("abstract", "") or s.get("title", "") for s in batch_sources]
        
        # Embed the batch with robust retry logic
        max_retries = 3
        vectors = None
        for attempt in range(max_retries):
            try:
                vectors = embeddings.embed_documents(texts)
                logger.debug("Successfully embedded batch %d", i)
                break
            except Exception as e:
                logger.warning("Embedding batch %d failed on attempt %d: %s. Quota hit, sleeping 40s...", i, attempt + 1, e)
                if attempt == max_retries - 1:
                    logger.error("Max retries reached. Failing this batch.")
                    raise
                time.sleep(40)

        if not vectors:
            continue

        for source, vec in zip(batch_sources, vectors):
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
            
        # Prevent spamming the API too fast within a single minute
        if i + BATCH_SIZE < len(sources):
            time.sleep(2)

    index.upsert(vectors=upsert_data, namespace=namespace)
    logger.info("Upserted %d vectors into Pinecone (namespace: '%s')", len(upsert_data), namespace)


def retrieve(query: str, top_k: int = 10, namespace: str = "") -> list[dict[str, Any]]:
    """Retrieve the most semantically relevant sources for a query.

    Returns a list of metadata dicts ranked by similarity.
    If namespace is provided, searches only within that namespace.
    """
    index = _get_pinecone_index()
    embeddings = _get_embeddings()

    query_vec = embeddings.embed_query(query)
    results = index.query(vector=query_vec, top_k=top_k, include_metadata=True, namespace=namespace)

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
    logger.info("Retrieved %d results from Pinecone for: %s (namespace: '%s')", len(retrieved), query, namespace)
    return retrieved
