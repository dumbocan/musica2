"""
Authentication schemas for user registration, login, and token management.
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema with common fields."""
    name: str = Field(..., max_length=100)
    email: EmailStr = Field(..., max_length=150)


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=8, max_length=100)


class UserUpdate(BaseModel):
    """Schema for user profile updates."""
    name: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = Field(None, max_length=150)
    password: Optional[str] = Field(None, min_length=8, max_length=100)


class UserResponse(UserBase):
    """Schema for user API responses (excluding sensitive data)."""
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


class UserInDB(UserResponse):
    """Schema for user data including password hash (internal use only)."""
    password_hash: str


class LoginRequest(BaseModel):
    """Schema for user login request."""
    email: EmailStr = Field(..., max_length=150)
    password: str = Field(..., min_length=8, max_length=100)


class Token(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Token expiration time in seconds


class TokenData(BaseModel):
    """Schema for token payload data."""
    user_id: Optional[int] = None
    email: Optional[str] = None


class PasswordChange(BaseModel):
    """Schema for password change request."""
    current_password: str = Field(..., min_length=8, max_length=100)
    new_password: str = Field(..., min_length=8, max_length=100)


class MessageResponse(BaseModel):
    """Schema for simple message responses."""
    message: str
