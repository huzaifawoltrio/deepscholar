import asyncio
import logging
from app.services.vectorstore import embed_and_store

logging.basicConfig(level=logging.INFO)

test_sources = [{
    "title": "Test Paper",
    "authors": ["John Doe"],
    "date": "2024.01.01",
    "publication": "TestPub",
    "abstract": "This is a test abstract about AI in medicine.",
    "url": "https://test.url/123"
}]

if __name__ == "__main__":
    try:
        embed_and_store(test_sources)
        print("Done")
    except Exception as e:
        print("ERROR:", str(e))
