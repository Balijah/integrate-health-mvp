"""
Authentication API endpoints.

Handles user registration, login, and current user retrieval.
"""

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import CurrentUser, DbSession
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserResponse
from app.services.auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_user_by_email,
    update_user,
)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class UpdateMeRequest(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new user account with email, password, and full name.",
)
@limiter.limit("3/minute")
async def register(
    request: Request,
    user_data: UserCreate,
    db: DbSession,
) -> UserResponse:
    """
    Register a new user account.

    Args:
        user_data: User registration data
        db: Database session

    Returns:
        UserResponse: Created user data

    Raises:
        HTTPException: 400 if email already registered
    """
    # Check if email already exists
    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    user = await create_user(
        db=db,
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name,
    )

    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login to get access token",
    description="Authenticate with email and password to receive a JWT token.",
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    credentials: LoginRequest,
    db: DbSession,
) -> TokenResponse:
    """
    Authenticate user and return access token.

    Args:
        credentials: Login credentials (email and password)
        db: Database session

    Returns:
        TokenResponse: JWT access token

    Raises:
        HTTPException: 401 if credentials are invalid
    """
    user = await authenticate_user(
        db=db,
        email=credentials.email,
        password=credentials.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = create_access_token(str(user.id))

    return TokenResponse(access_token=access_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get the currently authenticated user's information.",
)
async def get_me(
    current_user: CurrentUser,
) -> UserResponse:
    """
    Get current authenticated user.

    Args:
        current_user: Authenticated user from token

    Returns:
        UserResponse: Current user data
    """
    return UserResponse.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update current user",
    description="Update the current user's name or email.",
)
async def update_me(
    data: UpdateMeRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> UserResponse:
    """Update the current authenticated user's profile."""
    if data.email and data.email != current_user.email:
        existing = await get_user_by_email(db, data.email)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            )
    user = await update_user(db, current_user, full_name=data.full_name, email=data.email, phone=data.phone)
    return UserResponse.model_validate(user)
