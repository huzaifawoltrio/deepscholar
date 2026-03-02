from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.core.config import settings

def test():
    try:
        e = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004", google_api_key=settings.GOOGLE_API_KEY)
        v = e.embed_query("test")
        print("text-embedding-004 dim:", len(v))
    except Exception as e:
        print("text-embedding-004 error", e)

    try:
        e2 = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=settings.GOOGLE_API_KEY)
        v2 = e2.embed_query("test")
        print("embedding-001 dim:", len(v2))
    except Exception as e:
        print("embedding-001 error", e)

if __name__ == "__main__":
    test()
