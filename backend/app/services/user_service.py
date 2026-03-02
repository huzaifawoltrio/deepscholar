from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.user import User
from app.schemas.user import UserCreate


async def create_user(db: AsyncSession, *, user_in: UserCreate) -> User:
    """
    Create a new user, raising if the email is already registered.
    """
    existing = await crud.user.get_by_email(db, email=user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )
    return await crud.user.create(db, obj_in=user_in)


async def get_user_by_id(db: AsyncSession, *, user_id: int) -> User:
    """
    Get a user by ID, raising 404 if not found.
    """
    user = await crud.user.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user


async def authenticate_user(
    db: AsyncSession, *, email: str, password: str
) -> Optional[User]:
    """
    Authenticate a user by email and password.
    Returns the User object or None if authentication fails.
    """
    return await crud.user.authenticate(db, email=email, password=password)
