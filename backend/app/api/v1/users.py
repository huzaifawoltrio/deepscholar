from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.api import deps
from app.models.user import User
from app.services import user_service
from app.utils.security import hash_password

router = APIRouter()


# ------------------------------------------------------------------ List users
@router.get(
    "/",
    response_model=List[schemas.User],
    summary="List all users (admin only)",
)
async def read_users(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    _admin: User = Depends(deps.require_admin),
) -> Any:
    """Retrieve a paginated list of users. **Admin only.**"""
    users = await crud.user.get_multi(db, skip=skip, limit=limit)
    return users


# ------------------------------------------------------------------ Create user
@router.post(
    "/",
    response_model=schemas.User,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (admin only)",
)
async def create_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_in: schemas.UserCreate,
    _admin: User = Depends(deps.require_admin),
) -> Any:
    """Create a new user with any role. **Admin only.**"""
    user = await user_service.create_user(db, user_in=user_in)
    return user


# ------------------------------------------------------------------ Get user by ID
@router.get(
    "/{user_id}",
    response_model=schemas.User,
    summary="Get a user by ID (admin only)",
)
async def read_user_by_id(
    user_id: int,
    db: AsyncSession = Depends(deps.get_db),
    _admin: User = Depends(deps.require_admin),
) -> Any:
    """Get a specific user by ID. **Admin only.**"""
    user = await user_service.get_user_by_id(db, user_id=user_id)
    return user


# ------------------------------------------------------------------ Update user
@router.put(
    "/{user_id}",
    response_model=schemas.User,
    summary="Update a user (admin only)",
)
async def update_user(
    user_id: int,
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_in: schemas.UserUpdate,
    _admin: User = Depends(deps.require_admin),
) -> Any:
    """Update user fields. **Admin only.**"""
    user = await crud.user.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    # If a new password was provided, hash it before updating
    update_data = user_in.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))
    user = await crud.user.update(db, db_obj=user, obj_in=update_data)
    return user


# ------------------------------------------------------------------ Delete user
@router.delete(
    "/{user_id}",
    response_model=schemas.User,
    summary="Delete a user (admin only)",
)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(deps.get_db),
    _admin: User = Depends(deps.require_admin),
) -> Any:
    """Delete a user by ID. **Admin only.**"""
    user = await crud.user.remove(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    return user
