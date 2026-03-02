import sys
print("starting", flush=True)
from app.services.tools.arxiv_tool import search_arxiv
print("imported", flush=True)
query = "artificial intelligence medical"
print("calling with query:", query, flush=True)
res = search_arxiv(query)
print("result:", res, flush=True)
