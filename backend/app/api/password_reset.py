"""
Password reset API endpoints.

Handles forgot password (request reset) and reset password (with token).
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from jose import jwt, JWTError
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DbSession
from app.config import get_settings
from app.models.user import User
from app.services.auth import hash_password

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

SUPPORT_EMAILS = [
    "burhankhan@integratehealth.ai",
    "hallesutton@integratehealth.ai",
]


def create_reset_token(user_id: str, email: str) -> str:
    """Create a short-lived JWT for password reset (1 hour)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=1)
    payload = {
        "sub": user_id,
        "email": email,
        "purpose": "password_reset",
        "exp": int(expire.timestamp()),
        "iat": int(now.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_reset_token(token: str) -> dict | None:
    """Decode and validate a password reset token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("purpose") != "password_reset":
            return None
        return payload
    except JWTError:
        return None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class ResetPasswordResponse(BaseModel):
    message: str


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Request password reset",
    description="Send a password reset link to the user's email.",
)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: DbSession,
) -> ForgotPasswordResponse:
    """
    Request a password reset. Generates a reset token and attempts to email it.
    Always returns success to prevent email enumeration.
    """
    result = await db.execute(
        select(User).where(User.email == request.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    
    if user is not None:
        reset_token = create_reset_token(str(user.id), user.email)
        reset_url = f"https://app.integratehealth.ai/reset-password?token={reset_token}"
        
        logger.info(f"Password reset requested for {request.email}")
        
        # Try to send via SES
        try:
            import boto3
            ses = boto3.client("ses", region_name="us-east-1")
            
            body_html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #4ac6d6, #2a8fa0); padding: 20px; border-radius: 12px 12px 0 0;">
                    <h2 style="color: white; margin: 0;">Password Reset</h2>
                </div>
                <div style="padding: 24px; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 0 0 12px 12px;">
                    <p>Hi {user.full_name},</p>
                    <p>We received a request to reset your password. Click the link below to set a new password:</p>
                    <p><a href="{reset_url}" style="display: inline-block; background: #4ac6d6; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold;">Reset Password</a></p>
                    <p style="color: #9ca3af; font-size: 12px;">This link expires in 1 hour. If you didn't request this, you can safely ignore this email.</p>
                </div>
            </body>
            </html>
            """
            
            ses.send_email(
                Source="noreply@integratehealth.ai",
                Destination={"ToAddresses": [request.email]},
                Message={
                    "Subject": {"Data": "Reset your Integrate Health password"},
                    "Body": {
                        "Html": {"Data": body_html},
                        "Text": {"Data": f"Reset your password: {reset_url}\n\nThis link expires in 1 hour."},
                    },
                },
            )
            logger.info(f"Password reset email sent to {request.email}")
        except Exception as e:
            logger.warning(f"Could not send reset email via SES: {e}")
            logger.info(f"Reset URL (for manual delivery): {reset_url}")
    else:
        logger.info(f"Password reset requested for non-existent email: {request.email}")
    
    # Always return same message to prevent email enumeration
    return ForgotPasswordResponse(
        message="If an account with that email exists, we've sent a password reset link."
    )


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    summary="Reset password with token",
    description="Reset the user's password using a valid reset token.",
)
async def reset_password(
    request: ResetPasswordRequest,
    db: DbSession,
) -> ResetPasswordResponse:
    """Reset password using a valid reset token."""
    payload = decode_reset_token(request.token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token. Please request a new reset link.",
        )
    
    user_id = payload["sub"]
    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )
    
    # Update password
    user.hashed_password = hash_password(request.new_password)
    await db.flush()
    
    logger.info(f"Password reset completed for {user.email}")
    
    return ResetPasswordResponse(message="Password has been reset successfully. You can now log in.")
