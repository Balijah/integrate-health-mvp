"""
Transcription service with Whisper and AWS Transcribe Medical fallback.

Provides audio transcription functionality via:
1. Self-hosted Whisper service on AWS GPU instances (primary)
2. AWS Transcribe Medical (fallback when Whisper unavailable)
"""

import logging
import time
import uuid
from pathlib import Path
from typing import Optional

import boto3
import httpx
from botocore.exceptions import ClientError

from app.config import get_settings

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Custom exception for transcription failures."""
    pass


def _transcribe_with_aws_transcribe(s3_uri: str, job_name: str) -> dict:
    """
    Transcribe audio using AWS Transcribe Medical.

    Args:
        s3_uri: S3 URI of the audio file (s3://bucket/key)
        job_name: Unique job name for the transcription

    Returns:
        dict with transcription results

    Raises:
        TranscriptionError: If transcription fails
    """
    settings = get_settings()

    try:
        transcribe_client = boto3.client(
            'transcribe',
            region_name=settings.aws_region
        )

        # Determine media format from S3 URI
        extension = Path(s3_uri).suffix.lower().lstrip('.')
        media_format_map = {
            'wav': 'wav',
            'mp3': 'mp3',
            'm4a': 'mp4',
            'webm': 'webm',
            'ogg': 'ogg',
        }
        media_format = media_format_map.get(extension, 'wav')

        logger.info(f"Starting AWS Transcribe Medical job: {job_name}")

        # Start transcription job
        transcribe_client.start_medical_transcription_job(
            MedicalTranscriptionJobName=job_name,
            LanguageCode=settings.aws_transcribe_language_code,
            MediaFormat=media_format,
            Media={'MediaFileUri': s3_uri},
            OutputBucketName=settings.s3_bucket_name,
            OutputKey=f"transcriptions/{job_name}.json",
            Specialty=settings.aws_transcribe_medical_specialty,
            Type='DICTATION',  # DICTATION for medical notes, CONVERSATION for dialogue
        )

        # Poll for completion
        max_wait_seconds = 600  # 10 minutes max
        poll_interval = 5
        elapsed = 0

        while elapsed < max_wait_seconds:
            response = transcribe_client.get_medical_transcription_job(
                MedicalTranscriptionJobName=job_name
            )
            status = response['MedicalTranscriptionJob']['TranscriptionJobStatus']

            if status == 'COMPLETED':
                logger.info(f"AWS Transcribe job completed: {job_name}")
                break
            elif status == 'FAILED':
                failure_reason = response['MedicalTranscriptionJob'].get(
                    'FailureReason', 'Unknown error'
                )
                raise TranscriptionError(f"AWS Transcribe failed: {failure_reason}")

            time.sleep(poll_interval)
            elapsed += poll_interval

        if elapsed >= max_wait_seconds:
            raise TranscriptionError("AWS Transcribe job timed out")

        # Get transcript from S3
        s3_client = boto3.client('s3', region_name=settings.aws_region)
        transcript_key = f"transcriptions/{job_name}.json"

        response = s3_client.get_object(
            Bucket=settings.s3_bucket_name,
            Key=transcript_key
        )

        import json
        transcript_data = json.loads(response['Body'].read().decode('utf-8'))

        # Extract transcript text
        results = transcript_data.get('results', {})
        transcripts = results.get('transcripts', [])
        transcript_text = transcripts[0].get('transcript', '') if transcripts else ''

        # Clean up transcript file from S3
        try:
            s3_client.delete_object(
                Bucket=settings.s3_bucket_name,
                Key=transcript_key
            )
        except Exception as e:
            logger.warning(f"Failed to clean up transcript file: {e}")

        return {
            "transcript": transcript_text,
            "raw_transcript": transcript_text,
            "words": [],
            "speakers": [],
            "metadata": {
                "duration_seconds": 0,
                "channels": 1,
                "model": "aws-transcribe-medical",
                "language": settings.aws_transcribe_language_code,
                "request_id": job_name,
            },
        }

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = e.response.get('Error', {}).get('Message', str(e))
        logger.error(f"AWS Transcribe error: {error_code} - {error_msg}")
        raise TranscriptionError(f"AWS Transcribe error: {error_msg}")
    except TranscriptionError:
        raise
    except Exception as e:
        logger.error(f"AWS Transcribe failed: {type(e).__name__}: {str(e)}")
        raise TranscriptionError(f"Transcription failed: {str(e)}") from e


def _check_whisper_available() -> bool:
    """Check if Whisper service is available."""
    settings = get_settings()
    try:
        with httpx.Client(timeout=5) as client:
            response = client.get(f"{settings.whisper_service_url}/health")
            return response.status_code == 200
    except Exception:
        return False


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

    Uses Whisper service if available, otherwise falls back to AWS Transcribe Medical.

    Args:
        s3_key: S3 object key for the audio file.

    Returns:
        dict with transcription results.

    Raises:
        TranscriptionError: If transcription fails.
    """
    settings = get_settings()

    # Check if Whisper is available
    whisper_available = _check_whisper_available()

    # Use configured provider or auto-detect
    use_whisper = (
        settings.transcription_provider == "whisper" and whisper_available
    )
    use_aws_transcribe = (
        settings.transcription_provider == "aws_transcribe" or
        (settings.transcription_provider == "whisper" and not whisper_available)
    )

    if use_whisper:
        logger.info("Using Whisper for transcription")
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

            # Transcribe with Whisper
            return transcribe_audio(audio_bytes, mime_type)

        except S3StorageError as e:
            raise TranscriptionError(f"Failed to download audio: {str(e)}") from e

    elif use_aws_transcribe:
        if not whisper_available:
            logger.warning("Whisper unavailable, falling back to AWS Transcribe Medical")
        else:
            logger.info("Using AWS Transcribe Medical for transcription")

        # Use AWS Transcribe Medical
        s3_uri = f"s3://{settings.s3_bucket_name}/{s3_key}"
        job_name = f"ih-{uuid.uuid4().hex[:12]}"

        return _transcribe_with_aws_transcribe(s3_uri, job_name)

    else:
        raise TranscriptionError(
            "No transcription provider available. "
            "Whisper service is not running and AWS Transcribe is not configured."
        )
