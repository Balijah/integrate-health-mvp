"""
S3 Storage service for audio file management.

Provides async upload, download, and management of audio files in S3.
"""

import logging
from datetime import datetime
from typing import Optional

import boto3
from botocore.exceptions import ClientError, BotoCoreError

from app.config import get_settings

logger = logging.getLogger(__name__)


class S3StorageError(Exception):
    """Custom exception for S3 storage failures."""
    pass


def get_s3_client():
    """
    Get a boto3 S3 client.

    Returns:
        boto3 S3 client configured for the application region.
    """
    settings = get_settings()
    return boto3.client("s3", region_name=settings.aws_region)


def _get_extension_from_mime(mime_type: str) -> str:
    """
    Get file extension from MIME type.

    Args:
        mime_type: Audio MIME type.

    Returns:
        File extension including the dot.
    """
    extensions = {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mp3": ".mp3",
        "audio/mpeg": ".mp3",
        "audio/webm": ".webm",
        "audio/mp4": ".m4a",
        "audio/x-m4a": ".m4a",
        "audio/ogg": ".ogg",
    }
    return extensions.get(mime_type, ".wav")


def generate_s3_key(visit_id: str, mime_type: str) -> str:
    """
    Generate a unique S3 key for an audio file.

    Args:
        visit_id: Visit UUID.
        mime_type: Audio MIME type.

    Returns:
        S3 object key.
    """
    settings = get_settings()
    extension = _get_extension_from_mime(mime_type)
    timestamp = datetime.utcnow().strftime("%Y%m%d")

    # Format: audio/2024/01/visit_id.wav
    return f"{settings.s3_audio_prefix}{timestamp[:4]}/{timestamp[4:6]}/{visit_id}{extension}"


def upload_audio(file_bytes: bytes, visit_id: str, mime_type: str) -> str:
    """
    Upload audio to S3.

    Args:
        file_bytes: Raw audio file bytes.
        visit_id: Visit UUID.
        mime_type: Audio MIME type.

    Returns:
        S3 key of the uploaded file.

    Raises:
        S3StorageError: If upload fails.
    """
    settings = get_settings()

    if not settings.s3_bucket_name:
        raise S3StorageError(
            "S3 bucket not configured. Set S3_BUCKET_NAME in environment."
        )

    s3_key = generate_s3_key(visit_id, mime_type)

    try:
        s3 = get_s3_client()

        logger.info(f"Uploading audio to S3: {s3_key}")

        s3.put_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
            Body=file_bytes,
            ContentType=mime_type,
            ServerSideEncryption="AES256",  # Ensure encryption at rest
            Metadata={
                "visit_id": visit_id,
                "uploaded_at": datetime.utcnow().isoformat(),
            },
        )

        logger.info(f"Audio uploaded successfully: {s3_key}")
        return s3_key

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"S3 upload failed (ClientError): {error_code}")
        raise S3StorageError(f"Failed to upload audio: {error_code}") from e

    except BotoCoreError as e:
        logger.error(f"S3 upload failed (BotoCoreError): {str(e)}")
        raise S3StorageError("Failed to upload audio to S3") from e


def download_audio(s3_key: str) -> bytes:
    """
    Download audio from S3.

    Args:
        s3_key: S3 object key.

    Returns:
        Raw audio file bytes.

    Raises:
        S3StorageError: If download fails or file not found.
    """
    settings = get_settings()

    if not settings.s3_bucket_name:
        raise S3StorageError(
            "S3 bucket not configured. Set S3_BUCKET_NAME in environment."
        )

    try:
        s3 = get_s3_client()

        logger.info(f"Downloading audio from S3: {s3_key}")

        response = s3.get_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
        )

        audio_bytes = response["Body"].read()
        logger.info(f"Audio downloaded successfully: {len(audio_bytes)} bytes")

        return audio_bytes

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "NoSuchKey":
            logger.error(f"Audio file not found in S3: {s3_key}")
            raise S3StorageError("Audio file not found") from e
        logger.error(f"S3 download failed: {error_code}")
        raise S3StorageError(f"Failed to download audio: {error_code}") from e

    except BotoCoreError as e:
        logger.error(f"S3 download failed: {str(e)}")
        raise S3StorageError("Failed to download audio from S3") from e


def delete_audio(s3_key: str) -> None:
    """
    Delete audio from S3.

    Args:
        s3_key: S3 object key.

    Raises:
        S3StorageError: If deletion fails.
    """
    settings = get_settings()

    if not settings.s3_bucket_name:
        raise S3StorageError(
            "S3 bucket not configured. Set S3_BUCKET_NAME in environment."
        )

    try:
        s3 = get_s3_client()

        logger.info(f"Deleting audio from S3: {s3_key}")

        s3.delete_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
        )

        logger.info(f"Audio deleted successfully: {s3_key}")

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"S3 delete failed: {error_code}")
        raise S3StorageError(f"Failed to delete audio: {error_code}") from e

    except BotoCoreError as e:
        logger.error(f"S3 delete failed: {str(e)}")
        raise S3StorageError("Failed to delete audio from S3") from e


def generate_presigned_url(
    s3_key: str,
    expiration: int = 3600,
    method: str = "get_object"
) -> str:
    """
    Generate a presigned URL for temporary access to an audio file.

    Args:
        s3_key: S3 object key.
        expiration: URL expiration time in seconds (default 1 hour).
        method: S3 operation ("get_object" or "put_object").

    Returns:
        Presigned URL string.

    Raises:
        S3StorageError: If URL generation fails.
    """
    settings = get_settings()

    if not settings.s3_bucket_name:
        raise S3StorageError(
            "S3 bucket not configured. Set S3_BUCKET_NAME in environment."
        )

    try:
        s3 = get_s3_client()

        url = s3.generate_presigned_url(
            method,
            Params={
                "Bucket": settings.s3_bucket_name,
                "Key": s3_key,
            },
            ExpiresIn=expiration,
        )

        return url

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"Failed to generate presigned URL: {error_code}")
        raise S3StorageError(f"Failed to generate URL: {error_code}") from e


def check_audio_exists(s3_key: str) -> bool:
    """
    Check if an audio file exists in S3.

    Args:
        s3_key: S3 object key.

    Returns:
        True if file exists, False otherwise.
    """
    settings = get_settings()

    if not settings.s3_bucket_name:
        return False

    try:
        s3 = get_s3_client()
        s3.head_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
        )
        return True

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code in ("404", "NoSuchKey"):
            return False
        logger.error(f"Error checking S3 object: {error_code}")
        return False


def get_audio_metadata(s3_key: str) -> Optional[dict]:
    """
    Get metadata for an audio file in S3.

    Args:
        s3_key: S3 object key.

    Returns:
        Dict with metadata (content_type, size, last_modified, etc.) or None.
    """
    settings = get_settings()

    if not settings.s3_bucket_name:
        return None

    try:
        s3 = get_s3_client()
        response = s3.head_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
        )

        return {
            "content_type": response.get("ContentType"),
            "content_length": response.get("ContentLength"),
            "last_modified": response.get("LastModified"),
            "metadata": response.get("Metadata", {}),
        }

    except ClientError:
        return None
