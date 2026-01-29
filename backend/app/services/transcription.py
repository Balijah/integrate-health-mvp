"""
Transcription service using Deepgram API.

Provides audio transcription functionality with medical model support.
"""

import logging
from pathlib import Path

from deepgram import DeepgramClient, PrerecordedOptions, FileSource

from app.config import get_settings

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Custom exception for transcription failures."""

    pass


def transcribe_audio(audio_bytes: bytes, mime_type: str) -> dict:
    """
    Transcribe audio using Deepgram's medical model.

    This is a synchronous function for use in background tasks.

    Args:
        audio_bytes: Raw audio file bytes.
        mime_type: Audio MIME type (e.g., audio/webm, audio/wav).

    Returns:
        dict with 'transcript', 'words', 'metadata', and 'speakers'.

    Raises:
        TranscriptionError: If transcription fails.
    """
    settings = get_settings()

    if not settings.deepgram_api_key:
        raise TranscriptionError(
            "Deepgram API key not configured. Set DEEPGRAM_API_KEY in environment."
        )

    try:
        # Initialize Deepgram client
        deepgram = DeepgramClient(settings.deepgram_api_key)

        # Configure transcription options
        # Using nova-2-medical for medical terminology optimization
        options = PrerecordedOptions(
            model="nova-2-medical",
            language="en-US",
            smart_format=True,  # Automatic punctuation and formatting
            diarize=True,  # Speaker separation
            punctuate=True,
            utterances=True,  # Sentence boundaries
            paragraphs=True,
        )

        # Prepare audio source
        payload: FileSource = {
            "buffer": audio_bytes,
            "mimetype": mime_type,
        }

        # Call Deepgram API (using prerecorded endpoint)
        logger.info("Starting Deepgram transcription...")
        response = deepgram.listen.prerecorded.v("1").transcribe_file(payload, options)

        # Extract results
        result = response.to_dict()

        # Get the transcript text
        transcript = ""
        words = []
        speakers = set()

        if result.get("results", {}).get("channels"):
            channel = result["results"]["channels"][0]
            if channel.get("alternatives"):
                alternative = channel["alternatives"][0]
                transcript = alternative.get("transcript", "")
                words = alternative.get("words", [])

                # Extract unique speakers
                for word in words:
                    if "speaker" in word:
                        speakers.add(word["speaker"])

        # Build formatted transcript with speaker labels if diarization worked
        formatted_transcript = transcript
        if len(speakers) > 1 and result.get("results", {}).get("utterances"):
            utterances = result["results"]["utterances"]
            formatted_lines = []
            for utterance in utterances:
                speaker = utterance.get("speaker", 0)
                text = utterance.get("transcript", "")
                formatted_lines.append(f"Speaker {speaker}: {text}")
            formatted_transcript = "\n\n".join(formatted_lines)

        # Extract metadata
        metadata = {
            "duration_seconds": result.get("metadata", {}).get("duration", 0),
            "channels": result.get("metadata", {}).get("channels", 1),
            "model": result.get("metadata", {}).get("model_info", {}).get("name", "nova-2-medical"),
            "request_id": result.get("metadata", {}).get("request_id", ""),
        }

        logger.info(
            f"Transcription completed. Duration: {metadata['duration_seconds']}s, "
            f"Speakers: {len(speakers)}"
        )

        return {
            "transcript": formatted_transcript,
            "raw_transcript": transcript,
            "words": words,
            "speakers": list(speakers),
            "metadata": metadata,
        }

    except Exception as e:
        logger.error(f"Transcription failed: {type(e).__name__}")
        raise TranscriptionError("Transcription failed. Please try again.") from e


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

    mime_type = mime_types.get(path.suffix.lower(), "audio/webm")

    # Read file and transcribe
    audio_bytes = path.read_bytes()
    return transcribe_audio(audio_bytes, mime_type)
