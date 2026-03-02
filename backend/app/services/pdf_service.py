import logging
import re
import urllib.request
import tempfile
import os
from typing import List
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

def extract_arxiv_id(url: str) -> str | None:
    """Extract the arXiv ID from a URL (e.g. from https://arxiv.org/abs/2103.15348)."""
    match = re.search(r"arxiv\.org/(?:abs|pdf)/(\d+\.\d+)", url)
    return match.group(1) if match else None

def fetch_and_split_pdf(arxiv_url: str) -> List[dict]:
    """
    Downloads an arXiv PDF, parses it, and splits it into chunks.
    Returns a list of dicts with 'page_content' and 'metadata'.
    """
    arxiv_id = extract_arxiv_id(arxiv_url)
    if not arxiv_id:
        raise ValueError(f"Could not extract arXiv ID from {arxiv_url}")

    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    logger.info("Downloading PDF from %s", pdf_url)
    
    # Download the PDF to a temporary file
    fd, temp_path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        urllib.request.urlretrieve(pdf_url, temp_path)
        
        # Load and split the PDF
        loader = PyPDFLoader(temp_path)
        documents = loader.load()
        logger.info("Loaded %d pages from PDF", len(documents))

        # Limit to the first 30 pages to avoid quota issues on massive papers
        if len(documents) > 30:
            logger.info("Truncating PDF from %d to 30 pages to fit limits", len(documents))
            documents = documents[:30]

        # Split into larger chunks with overlap to drastically reduce API embedding calls
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=3000,
            chunk_overlap=400,
            separators=["\n\n", "\n", ".", " ", ""],
        )
        splits = text_splitter.split_documents(documents)
        logger.info("Split PDF into %d chunks", len(splits))
        
        return [{"page_content": doc.page_content, "metadata": doc.metadata} for doc in splits]
    except Exception as e:
        logger.error("Error processing PDF: %s", e)
        raise
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
