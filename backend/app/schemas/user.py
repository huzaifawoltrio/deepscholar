from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


# ---------- Shared properties ----------
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    role: str = "client"


# ---------- Create (admin use — allows setting role) ----------
class UserCreate(UserBase):
    password: str


# ---------- Register (public — role is always "client") ----------
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


# ---------- Update ----------
class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[str] = None


# ---------- Read (returned by API) ----------
class User(UserBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Auth Schemas ----------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[str] = None


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordReset(BaseModel):
    token: str
    new_password: str
