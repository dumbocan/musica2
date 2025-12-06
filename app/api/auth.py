"""
Authentication API endpoints for user registration, login, and management.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import SessionDep
from app.core.security import (
    get_password_hash, 
    verify_password, 
    create_user_token,
    get_current_user_id
)
from app.models.base import User
from app.schemas.auth import (
    UserCreate, 
    UserResponse, 
    UserUpdate,
    LoginRequest, 
    Token,
    PasswordChange,
    MessageResponse,
    UserInDB
)

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    session: AsyncSession = Depends(SessionDep)
):
    """
    Register a new user.
    
    - **name**: User's full name (required, max 100 chars)
    - **email**: User's email address (required, unique)
    - **password**: Password (required, min 8 chars)
    """
    # Check if user already exists
    result = await session.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hashed_password
    )
    
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    
    return new_user


@router.post("/login", response_model=Token)
async def login_user(
    login_data: LoginRequest,
    session: AsyncSession = Depends(SessionDep)
):
    """
    Authenticate user and return JWT token.
    
    - **email**: User's email address
    - **password**: User's password
    """
    # Find user by email
    result = await session.execute(
        select(User).where(User.email == login_data.email)
    )
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token = create_user_token(user_id=user.id, email=user.email)
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 1800  # 30 minutes in seconds
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(SessionDep)
):
    """
    Get current user's profile information.
    Requires valid JWT token.
    """
    result = await session.execute(
        select(User).where(User.id == current_user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_data: UserUpdate,
    current_user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(SessionDep)
):
    """
    Update current user's profile.
    Requires valid JWT token.
    """
    result = await session.execute(
        select(User).where(User.id == current_user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update fields if provided
    update_data = user_data.dict(exclude_unset=True)
    
    # Check for email uniqueness if email is being updated
    if "email" in update_data and update_data["email"] != user.email:
        email_result = await session.execute(
            select(User).where(User.email == update_data["email"])
        )
        existing_user = email_result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Hash password if provided
    if "password" in update_data:
        update_data["password_hash"] = get_password_hash(update_data.pop("password"))
    
    # Update user
    for field, value in update_data.items():
        setattr(user, field, value)
    
    await session.commit()
    await session.refresh(user)
    
    return user


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    password_data: PasswordChange,
    current_user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(SessionDep)
):
    """
    Change current user's password.
    Requires valid JWT token.
    """
    result = await session.execute(
        select(User).where(User.id == current_user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify current password
    if not verify_password(password_data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Update password
    user.password_hash = get_password_hash(password_data.new_password)
    await session.commit()
    
    return {"message": "Password updated successfully"}


@router.get("/verify-token", response_model=MessageResponse)
async def verify_auth_token(current_user_id: int = Depends(get_current_user_id)):
    """
    Verify that the provided JWT token is valid.
    """
    return {"message": "Token is valid"}


@router.delete("/me", response_model=MessageResponse)
async def delete_current_user(
    current_user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(SessionDep)
):
    """
    Delete current user's account.
    Requires valid JWT token.
    """
    result = await session.execute(
        select(User).where(User.id == current_user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Delete user (cascade will handle related records)
    await session.delete(user)
    await session.commit()
    
    return {"message": "User account deleted successfully"}


@router.get("/health", response_model=MessageResponse)
async def auth_health_check():
    """
    Health check for authentication service.
    """
    return {"message": "Authentication service is running"}
