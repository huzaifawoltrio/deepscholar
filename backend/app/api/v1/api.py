from fastapi import APIRouter

from app.api.v1 import auth, users, research, chat, papers

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(research.router, prefix="/research", tags=["Research"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(papers.router, prefix="/papers", tags=["Papers"])
