"""Direct PDF Chat execution endpoints."""

import logging
import traceback
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.api import deps
from app.models.user import User
from app.services.pdf_service import fetch_and_split_pdf
from app.services.vectorstore import embed_and_store, retrieve
from app.core.config import settings
import hashlib

logger = logging.getLogger(__name__)

router = APIRouter()

class PaperChatRequest(BaseModel):
    url: str
    query: str
    history: list[dict] = []

class PaperChatResponse(BaseModel):
    response: str
    namespace: str

def generate_namespace(url: str) -> str:
    """Generate a deterministic namespace hash from the URL."""
    return hashlib.md5(url.encode()).hexdigest()

@router.post("/chat", response_model=PaperChatResponse, summary="Chat directly with an arXiv paper")
async def chat_with_paper(
    body: PaperChatRequest,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    try:
        namespace = generate_namespace(body.url)
        
        # 1. Ensure the PDF is embedded in Pinecone
        # Since Pinecone lists namespaces per-index, we try retrieving first.
        # If no results, we assume we need to embed.
        existing_chunks = retrieve("test", top_k=1, namespace=namespace)
        if not existing_chunks:
            logger.info("Namespace %s empty. Fetching and embedding PDF...", namespace)
            chunks = fetch_and_split_pdf(body.url)
            
            # Format chunks to match vectorstore schema
            formatted_sources = [
                {
                    "title": chunk["metadata"].get("source", body.url),
                    "abstract": chunk["page_content"],
                    "url": body.url,
                    "authors": [],
                    "publication": "arXiv",
                    "date": ""
                }
                for chunk in chunks
            ]
            embed_and_store(formatted_sources, namespace=namespace)
        else:
            logger.info("Namespace %s already populated.", namespace)

        # 2. Retrieve relevant chunks for the query
        relevant_docs = retrieve(body.query, top_k=5, namespace=namespace)
        context_text = "\n\n".join([f"--- Excerpt ---\n{doc.get('abstract', '')}\n" for doc in relevant_docs])

        # 3. Generate response using Gemini
        llm = ChatGoogleGenerativeAI(
            model=settings.LLM_MODEL, 
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.2
        )

        messages = [
            SystemMessage(content=(
                "You are an expert academic research assistant answering questions specifically about a provided paper. "
                "Use the provided excerpts from the document to answer the user's question accurately. "
                "If the answer cannot be found in the context, explicitly state that."
                f"\n\nContext from Paper:\n{context_text}"
            ))
        ]

        for msg in body.history[-5:]: # Only take the last 5 messages for context
            if msg.get("role") == "user":
                messages.append(HumanMessage(content=msg.get("content", "")))
            elif msg.get("role") == "assistant":
                messages.append(AIMessage(content=msg.get("content", "")))

        messages.append(HumanMessage(content=body.query))

        response = await llm.ainvoke(messages)
        return {"response": str(response.content), "namespace": namespace}

    except Exception as exc:
        logger.error(
            "Paper chat failed for url '%s': %s\n%s",
            body.url, exc, traceback.format_exc(),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Paper chat processing failed: {str(exc)}",
        )
