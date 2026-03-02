from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, schemas
from app.api import deps
from app.models.user import User
from app.utils.security import (
    create_access_token,
    create_password_reset_token,
    verify_password_reset_token,
    hash_password,
)

router = APIRouter()


# ------------------------------------------------------------------ Register
@router.post(
    "/register",
    response_model=schemas.User,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new client account",
)
async def register(
    *,
    db: AsyncSession = Depends(deps.get_db),
    user_in: schemas.UserRegister,
) -> Any:
    """Public registration endpoint. Always creates a **client** user."""
    existing = await crud.user.get_by_email(db, email=user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )
    user_create = schemas.UserCreate(
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
        role="client",
    )
    return await crud.user.create(db, obj_in=user_create)


# ------------------------------------------------------------------ Login
@router.post(
    "/login",
    response_model=schemas.Token,
    summary="Login and receive a JWT access token",
)
async def login(
    *,
    db: AsyncSession = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """
    OAuth2-compatible login.
    Send `username` (email) and `password` as form data.
    """
    user = await crud.user.authenticate(
        db, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user.",
        )
    access_token = create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer"}


# ------------------------------------------------------------------ Me
@router.get(
    "/me",
    response_model=schemas.User,
    summary="Get current authenticated user profile",
)
async def read_current_user(
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """Return the currently authenticated user."""
    return current_user


# --------------------------------------------------------- Forgot Password
@router.post(
    "/forgot-password",
    summary="Request a password reset token",
)
async def forgot_password(
    *,
    db: AsyncSession = Depends(deps.get_db),
    body: schemas.PasswordResetRequest,
) -> Any:
    """
    Generate a password-reset token for the given email.

    In production this token would be sent via email.
    For development the token is returned directly in the response.
    """
    user = await crud.user.get_by_email(db, email=body.email)
    if not user:
        # Don't reveal whether the email exists — return success either way
        return {"message": "If that email is registered, a reset link has been sent."}

    reset_token = create_password_reset_token(email=user.email)
    # Log it for development convenience
    print(f"[DEV] Password-reset token for {user.email}: {reset_token}")

    return {
        "message": "If that email is registered, a reset link has been sent.",
        "reset_token": reset_token,  # remove in production
    }


# --------------------------------------------------------- Reset Password
@router.post(
    "/reset-password",
    summary="Reset password using a reset token",
)
async def reset_password(
    *,
    db: AsyncSession = Depends(deps.get_db),
    body: schemas.PasswordReset,
) -> Any:
    """Verify the reset token and set a new password."""
    email = verify_password_reset_token(body.token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )
    user = await crud.user.get_by_email(db, email=email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user.",
        )
    hashed = hash_password(body.new_password)
    await crud.user.update_password(db, user=user, new_hashed_password=hashed)
    return {"message": "Password updated successfully."}
