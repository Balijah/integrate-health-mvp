"""
Services package.

Contains business logic for the application.
"""

from app.services.auth import (
    authenticate_user,
    create_access_token,
    create_user,
    decode_access_token,
    get_user_by_email,
    get_user_by_id,
    hash_password,
    verify_password,
)
from app.services.transcription import (
    TranscriptionError,
    transcribe_audio,
    transcribe_audio_file,
)

__all__ = [
    # Auth
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "authenticate_user",
    "get_user_by_email",
    "get_user_by_id",
    "create_user",
    # Transcription
    "TranscriptionError",
    "transcribe_audio",
    "transcribe_audio_file",
]
