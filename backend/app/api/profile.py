"""
Profile API endpoints.

Handles profile picture upload and profile updates.
"""

import logging
import uuid
import os

from fastapi import APIRouter, HTTPException, UploadFile, File, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None


class ProfileResponse(BaseModel):
    full_name: str
    email: str
    profile_picture_url: str | None


@router.post(
    "/profile/picture",
    response_model=ProfileResponse,
    summary="Upload profile picture",
    description="Upload a profile picture for the current user.",
)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: CurrentUser = None,
    db: DbSession = None,
) -> ProfileResponse:
    """Upload a profile picture. Stores in S3 or local uploads directory."""
    
    # Validate file type
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: JPEG, PNG, WebP, GIF",
        )
    
    # Read and validate size
    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 5MB.",
        )
    
    # Generate filename
    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg"
    filename = f"profile_{current_user.id}.{ext}"
    
    if settings.storage_mode == "s3" and settings.s3_bucket_name:
        # Upload to S3
        try:
            import boto3
            s3 = boto3.client("s3", region_name=settings.aws_region)
            key = f"profiles/{filename}"
            s3.put_object(
                Bucket=settings.s3_bucket_name,
                Key=key,
                Body=contents,
                ContentType=file.content_type,
            )
            picture_url = f"https://{settings.s3_bucket_name}.s3.amazonaws.com/{key}"
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload image")
    else:
        # Save locally
        upload_dir = os.path.join(settings.upload_dir, "profiles")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, "wb") as f:
            f.write(contents)
        picture_url = f"/uploads/profiles/{filename}"
    
    # Update user record
    current_user.profile_picture_url = picture_url
    await db.flush()
    await db.refresh(current_user)
    
    logger.info(f"Profile picture uploaded for user {current_user.email}: {picture_url}")
    
    return ProfileResponse(
        full_name=current_user.full_name,
        email=current_user.email,
        profile_picture_url=current_user.profile_picture_url,
    )
