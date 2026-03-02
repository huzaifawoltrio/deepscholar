from fastapi import APIRouter

from app.api.v1 import auth, users, research

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(research.router, prefix="/research", tags=["Research"])
