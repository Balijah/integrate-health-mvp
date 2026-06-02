"""
Authentication API endpoints.

Handles user registration, login, token refresh, and current user retrieval.
"""

import logging

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.models.audit_log import AuditLog
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserCreate, UserResponse
from app.services.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_user,
    decode_refresh_token,
    get_user_by_email,
    update_user,
)

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class UpdateMeRequest(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None


async def _audit(
    db: AsyncSession,
    event_type: str,
    request: Request,
    user_id: str | None = None,
    detail: str | None = None,
) -> None:
    try:
        forwarded_for = request.headers.get("X-Forwarded-For")
        ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else None)
        entry = AuditLog(
            user_id=user_id,
            event_type=event_type,
            ip_address=ip,
            user_agent=request.headers.get("User-Agent", "")[:500],
            detail=detail,
        )
        db.add(entry)
        await db.flush()
    except Exception as exc:
        logger.warning(f"[AUDIT] Failed to write audit log: {exc}")


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
    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user is not None:
        await _audit(db, "register_failed", request, detail="email_already_registered")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = await create_user(
        db=db,
        email=user_data.email,
        password=user_data.password,
        full_name=user_data.full_name,
    )

    await _audit(db, "register", request, user_id=str(user.id))
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login to get access token",
    description="Authenticate with email and password to receive a JWT token pair.",
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    credentials: LoginRequest,
    db: DbSession,
) -> TokenResponse:
    user = await authenticate_user(
        db=db,
        email=credentials.email,
        password=credentials.password,
    )

    if user is None:
        await _audit(db, "login_failed", request, detail=credentials.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await _audit(db, "login", request, user_id=str(user.id))
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Exchange a valid refresh token for a new access + refresh token pair.",
)
@limiter.limit("10/minute")
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    db: DbSession,
) -> TokenResponse:
    payload = decode_refresh_token(body.refresh_token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    await _audit(db, "token_refresh", request, user_id=payload.sub)
    access_token = create_access_token(payload.sub)
    new_refresh_token = create_refresh_token(payload.sub)
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get the currently authenticated user's information.",
)
async def get_me(
    current_user: CurrentUser,
) -> UserResponse:
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
    if data.email and data.email != current_user.email:
        existing = await get_user_by_email(db, data.email)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            )
    user = await update_user(db, current_user, full_name=data.full_name, email=data.email, phone=data.phone)
    return UserResponse.model_validate(user)
