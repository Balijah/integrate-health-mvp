"""
Transcription service using Deepgram Nova-2 Medical.

Provides audio transcription via the Deepgram managed API with support for
raw audio bytes, local file paths, and S3-hosted audio (via presigned URL).
"""

import logging
from pathlib import Path

import boto3

from app.config import get_settings

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Custom exception for transcription failures."""
    pass


def _mime_from_path(path: Path) -> str:
    mime_types = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".webm": "audio/webm",
        ".ogg": "audio/ogg",
    }
    return mime_types.get(path.suffix.lower(), "audio/wav")


def _get_deepgram_options():
    from deepgram import PrerecordedOptions

    settings = get_settings()
    return PrerecordedOptions(
        model=settings.deepgram_model,
        language=settings.deepgram_language,
        smart_format=True,
        punctuate=True,
        diarize=True,
        utterances=True,
        paragraphs=True,
        filler_words=False,
        measurements=True,
    )


def _parse_deepgram_response(response) -> dict:
    """Extract transcript, segments, and metadata from a Deepgram 3.x response."""
    alt = response.results.channels[0].alternatives[0]
    transcript = alt.transcript or ""
    confidence = float(alt.confidence or 0.0)

    segments = []
    for utt in (response.results.utterances or []):
        segments.append({
            "speaker": f"Speaker {utt.speaker}",
            "start": utt.start,
            "end": utt.end,
            "text": utt.transcript,
            "confidence": float(utt.confidence or 0.0),
        })

    unique_speakers = len({s["speaker"] for s in segments}) if segments else 0
    duration = float(response.metadata.duration) if response.metadata else 0.0

    settings = get_settings()
    return {
        "transcript": transcript,
        "raw_transcript": transcript,
        "words": [],
        "speakers": segments,
        "metadata": {
            "duration_seconds": int(duration),
            "confidence": round(confidence, 4),
            "num_speakers": unique_speakers,
            "model": settings.deepgram_model,
            "language": settings.deepgram_language,
        },
    }


def transcribe_audio(audio_bytes: bytes, mime_type: str) -> dict:
    """
    Transcribe raw audio bytes using Deepgram.

    Args:
        audio_bytes: Raw audio file bytes.
        mime_type: Audio MIME type (e.g., audio/webm, audio/wav).

    Returns:
        dict with 'transcript', 'raw_transcript', 'words', 'speakers', 'metadata'.

    Raises:
        TranscriptionError: If transcription fails.
    """
    from deepgram import DeepgramClient

    settings = get_settings()

    if not settings.deepgram_api_key:
        raise TranscriptionError(
            "Deepgram API key not configured. Set DEEPGRAM_API_KEY in environment."
        )

    try:
        logger.info(f"Starting Deepgram transcription ({len(audio_bytes)} bytes)...")
        deepgram = DeepgramClient(settings.deepgram_api_key)
        payload = {"buffer": audio_bytes}
        response = deepgram.listen.rest.v("1").transcribe_file(payload, _get_deepgram_options())
        result = _parse_deepgram_response(response)
        logger.info(
            f"Transcription completed. Duration: {result['metadata']['duration_seconds']}s, "
            f"Confidence: {result['metadata']['confidence']}, "
            f"Speakers: {result['metadata']['num_speakers']}"
        )
        return result
    except TranscriptionError:
        raise
    except Exception as e:
        logger.error(f"Deepgram transcription failed: {type(e).__name__}: {str(e)}")
        raise TranscriptionError(f"Transcription failed: {str(e)}") from e


def transcribe_audio_file(file_path: str) -> dict:
    """
    Transcribe audio from a local file path.

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

    return transcribe_audio(path.read_bytes(), _mime_from_path(path))


def transcribe_from_s3(s3_key: str) -> dict:
    """
    Transcribe audio from S3 using a presigned URL (no download needed).

    Args:
        s3_key: S3 object key for the audio file.

    Returns:
        dict with transcription results.

    Raises:
        TranscriptionError: If transcription fails.
    """
    from deepgram import DeepgramClient

    settings = get_settings()

    if not settings.deepgram_api_key:
        raise TranscriptionError(
            "Deepgram API key not configured. Set DEEPGRAM_API_KEY in environment."
        )

    try:
        s3_client = boto3.client("s3", region_name=settings.aws_region)
        audio_url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket_name, "Key": s3_key},
            ExpiresIn=3600,
        )

        logger.info(f"Starting Deepgram S3 transcription for key: {s3_key}")
        deepgram = DeepgramClient(settings.deepgram_api_key)
        response = deepgram.listen.rest.v("1").transcribe_url(
            {"url": audio_url}, _get_deepgram_options()
        )
        result = _parse_deepgram_response(response)
        logger.info(
            f"S3 transcription completed. Duration: {result['metadata']['duration_seconds']}s, "
            f"Confidence: {result['metadata']['confidence']}"
        )
        return result
    except TranscriptionError:
        raise
    except Exception as e:
        logger.error(f"Deepgram S3 transcription failed: {type(e).__name__}: {str(e)}")
        raise TranscriptionError(f"Transcription failed: {str(e)}") from e
