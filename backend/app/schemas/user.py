"""
User Pydantic schemas for request/response validation.

Defines schemas for user registration and user data responses.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for user registration request."""

    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (min 8 characters)",
    )
    full_name: str
    profile_picture_url: str | None = None = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User's full name",
    )


class UserResponse(BaseModel):
    """Schema for user data in responses."""

    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserInDB(UserResponse):
    """Schema for user data including hashed password (internal use)."""

    hashed_password: str
