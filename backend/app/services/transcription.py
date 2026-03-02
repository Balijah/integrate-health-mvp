"""
Transcription service using self-hosted Whisper.

Provides audio transcription functionality via a self-hosted Whisper service
running on AWS GPU instances.
"""

import logging
from pathlib import Path
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Custom exception for transcription failures."""
    pass


def transcribe_audio(audio_bytes: bytes, mime_type: str) -> dict:
    """
    Transcribe audio using the self-hosted Whisper service.

    This is a synchronous function for use in background tasks.

    Args:
        audio_bytes: Raw audio file bytes.
        mime_type: Audio MIME type (e.g., audio/webm, audio/wav).

    Returns:
        dict with 'transcript', 'raw_transcript', 'words', 'metadata', and 'speakers'.

    Raises:
        TranscriptionError: If transcription fails.
    """
    settings = get_settings()

    if not settings.whisper_service_url:
        raise TranscriptionError(
            "Whisper service URL not configured. Set WHISPER_SERVICE_URL in environment."
        )

    try:
        logger.info(f"Starting Whisper transcription ({len(audio_bytes)} bytes)...")

        # Prepare multipart form data
        files = {
            "audio": ("audio", audio_bytes, mime_type),
        }
        data = {
            "mime_type": mime_type,
        }

        # Call Whisper service with timeout
        with httpx.Client(timeout=settings.whisper_timeout_seconds) as client:
            response = client.post(
                f"{settings.whisper_service_url}/transcribe",
                files=files,
                data=data,
            )

        if response.status_code != 200:
            logger.error(f"Whisper service returned status {response.status_code}")
            raise TranscriptionError(
                f"Transcription service error (status {response.status_code})"
            )

        result = response.json()

        # Extract transcript text
        transcript = result.get("text", "").strip()

        if not transcript:
            logger.warning("Whisper returned empty transcript")

        # Get duration from result
        duration_seconds = result.get("duration", 0)

        # Format transcript with segments if available
        # Whisper provides segments but not speaker diarization by default
        formatted_transcript = transcript
        segments = result.get("segments", [])

        if segments:
            # Create a cleaner formatted version with segment breaks
            formatted_lines = []
            for segment in segments:
                text = segment.get("text", "").strip()
                if text:
                    formatted_lines.append(text)
            if formatted_lines:
                formatted_transcript = " ".join(formatted_lines)

        logger.info(
            f"Transcription completed. Duration: {duration_seconds}s, "
            f"Length: {len(transcript)} chars"
        )

        return {
            "transcript": formatted_transcript,
            "raw_transcript": transcript,
            "words": [],  # Whisper basic mode doesn't provide word-level timing
            "speakers": [],  # No diarization in basic Whisper
            "metadata": {
                "duration_seconds": duration_seconds,
                "channels": 1,
                "model": "whisper-large-v3",
                "language": result.get("language", "en"),
                "request_id": "",  # Whisper doesn't provide request IDs
            },
        }

    except httpx.TimeoutException:
        logger.error("Whisper service request timed out")
        raise TranscriptionError(
            "Transcription timed out. Audio may be too long."
        )

    except httpx.ConnectError:
        logger.error("Failed to connect to Whisper service")
        raise TranscriptionError(
            "Failed to connect to transcription service. Please try again."
        )

    except httpx.HTTPError as e:
        logger.error(f"HTTP error during transcription: {type(e).__name__}")
        raise TranscriptionError(
            "Transcription service communication error. Please try again."
        )

    except Exception as e:
        logger.error(f"Transcription failed: {type(e).__name__}: {str(e)}")
        raise TranscriptionError(
            "Transcription failed. Please try again."
        ) from e


def transcribe_audio_file(file_path: str) -> dict:
    """
    Transcribe audio from a file path.

    This is a synchronous function for use in background tasks.

    Args:
        file_path: Path to the audio file.

    Returns:
        dict with transcription results.

    Raises:
        TranscriptionError: If file not found or transcription fails.
    """
    path = Path(file_path)

    if not path.exists():
        raise TranscriptionError(f"Audio file not found: {file_path}")

    # Determine MIME type from extension
    mime_types = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".webm": "audio/webm",
        ".ogg": "audio/ogg",
    }

    mime_type = mime_types.get(path.suffix.lower(), "audio/wav")

    # Read file and transcribe
    audio_bytes = path.read_bytes()
    return transcribe_audio(audio_bytes, mime_type)


def check_whisper_service_health() -> dict:
    """
    Check if the Whisper service is healthy and available.

    Returns:
        dict with health status information.

    Raises:
        TranscriptionError: If service is unavailable.
    """
    settings = get_settings()

    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(f"{settings.whisper_service_url}/health")

        if response.status_code != 200:
            return {
                "status": "unhealthy",
                "error": f"Service returned status {response.status_code}",
            }

        return response.json()

    except httpx.ConnectError:
        return {
            "status": "unavailable",
            "error": "Cannot connect to Whisper service",
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


def transcribe_from_s3(s3_key: str) -> dict:
    """
    Transcribe audio file stored in S3.

    Downloads the audio from S3 and sends it to the Whisper service.

    Args:
        s3_key: S3 object key for the audio file.

    Returns:
        dict with transcription results.

    Raises:
        TranscriptionError: If download or transcription fails.
    """
    from app.services.s3_storage import download_audio, S3StorageError

    try:
        # Download audio from S3
        logger.info(f"Downloading audio from S3: {s3_key}")
        audio_bytes = download_audio(s3_key)

        # Determine MIME type from key extension
        mime_types = {
            ".wav": "audio/wav",
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".webm": "audio/webm",
            ".ogg": "audio/ogg",
        }

        extension = Path(s3_key).suffix.lower()
        mime_type = mime_types.get(extension, "audio/wav")

        # Transcribe
        return transcribe_audio(audio_bytes, mime_type)

    except S3StorageError as e:
        raise TranscriptionError(f"Failed to download audio: {str(e)}") from e
