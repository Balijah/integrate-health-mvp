"""
Audio file validation utilities.

Provides functions for validating uploaded audio files.
"""


# Supported audio MIME types and their file extensions
SUPPORTED_AUDIO_TYPES = {
    "audio/wav": [".wav"],
    "audio/x-wav": [".wav"],
    "audio/wave": [".wav"],
    "audio/mp3": [".mp3"],
    "audio/mpeg": [".mp3"],
    "audio/mp4": [".m4a", ".mp4"],
    "audio/x-m4a": [".m4a"],
    "audio/webm": [".webm"],
    "audio/ogg": [".ogg"],
}

# Maximum file size: 100MB
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024

# Minimum file size: 1KB (to reject empty/corrupt files)
MIN_FILE_SIZE_BYTES = 1024


def normalize_mime_type(mime_type: str) -> str:
    """
    Normalize MIME type by removing codec parameters.

    Browsers often send MIME types like 'audio/webm;codecs=opus'
    but we only need the base type 'audio/webm'.

    Args:
        mime_type: Full MIME type string, possibly with parameters.

    Returns:
        Base MIME type without parameters.
    """
    # Split on semicolon and take just the base type
    base_type = mime_type.split(";")[0].strip().lower()
    return base_type


def get_supported_mime_types() -> list[str]:
    """
    Get list of supported audio MIME types.

    Returns:
        List of supported MIME type strings.
    """
    return list(SUPPORTED_AUDIO_TYPES.keys())


def is_valid_mime_type(mime_type: str) -> bool:
    """
    Check if the MIME type is supported.

    Args:
        mime_type: MIME type string to validate (may include codec params).

    Returns:
        True if supported, False otherwise.
    """
    normalized = normalize_mime_type(mime_type)
    return normalized in SUPPORTED_AUDIO_TYPES


def validate_file_size(content: bytes) -> tuple[bool, str | None]:
    """
    Validate audio file size.

    Args:
        content: File content as bytes.

    Returns:
        Tuple of (is_valid, error_message).
    """
    size = len(content)

    if size < MIN_FILE_SIZE_BYTES:
        return False, f"File too small ({size} bytes). Minimum size is {MIN_FILE_SIZE_BYTES} bytes."

    if size > MAX_FILE_SIZE_BYTES:
        size_mb = size / (1024 * 1024)
        max_mb = MAX_FILE_SIZE_BYTES / (1024 * 1024)
        return False, f"File too large ({size_mb:.1f} MB). Maximum size is {max_mb:.0f} MB."

    return True, None


def detect_audio_format(content: bytes) -> str | None:
    """
    Detect audio format from file content magic bytes.

    Args:
        content: File content as bytes.

    Returns:
        Detected MIME type or None if unknown.
    """
    if len(content) < 12:
        return None

    # WAV: starts with "RIFF" and contains "WAVE"
    if content[:4] == b"RIFF" and content[8:12] == b"WAVE":
        return "audio/wav"

    # MP3: starts with ID3 tag or MP3 frame sync
    if content[:3] == b"ID3" or (content[0] == 0xFF and (content[1] & 0xE0) == 0xE0):
        return "audio/mpeg"

    # M4A/MP4: contains "ftyp" atom
    if content[4:8] == b"ftyp":
        # Check for specific M4A types
        ftyp = content[8:12]
        if ftyp in (b"M4A ", b"mp42", b"isom", b"mp41"):
            return "audio/mp4"

    # WebM: starts with EBML header
    if content[:4] == b"\x1a\x45\xdf\xa3":
        return "audio/webm"

    # OGG: starts with "OggS"
    if content[:4] == b"OggS":
        return "audio/ogg"

    return None


def validate_audio_content(content: bytes, claimed_mime_type: str) -> tuple[bool, str | None]:
    """
    Validate audio file content matches claimed MIME type.

    Args:
        content: File content as bytes.
        claimed_mime_type: MIME type claimed by the upload (may include codec params).

    Returns:
        Tuple of (is_valid, error_message).
    """
    detected_type = detect_audio_format(content)

    if detected_type is None:
        return False, "Unable to detect audio format. File may be corrupt or not a valid audio file."

    # Normalize claimed type (strip codec params like ;codecs=opus)
    claimed_lower = normalize_mime_type(claimed_mime_type)

    # Handle equivalent MIME types
    type_groups = [
        {"audio/wav", "audio/x-wav", "audio/wave"},
        {"audio/mp3", "audio/mpeg"},
        {"audio/mp4", "audio/x-m4a"},
    ]

    for group in type_groups:
        if claimed_lower in group and detected_type in group:
            return True, None

    # Direct match
    if detected_type == claimed_lower:
        return True, None

    # WebM and OGG can be flexible
    if detected_type in ("audio/webm", "audio/ogg") and claimed_lower in ("audio/webm", "audio/ogg"):
        return True, None

    return False, f"File content does not match claimed type. Expected {claimed_mime_type}, detected {detected_type}."


def validate_audio_file(
    content: bytes,
    mime_type: str,
    filename: str | None = None
) -> tuple[bool, str | None]:
    """
    Perform full validation of an audio file.

    Args:
        content: File content as bytes.
        mime_type: Claimed MIME type.
        filename: Optional filename for extension validation.

    Returns:
        Tuple of (is_valid, error_message).
    """
    # Check MIME type is supported
    if not is_valid_mime_type(mime_type):
        supported = ", ".join(get_supported_mime_types())
        return False, f"Unsupported audio format: {mime_type}. Supported formats: {supported}"

    # Check file size
    is_valid, error = validate_file_size(content)
    if not is_valid:
        return False, error

    # Validate content matches MIME type
    is_valid, error = validate_audio_content(content, mime_type)
    if not is_valid:
        return False, error

    return True, None


def get_audio_duration_estimate(content: bytes, mime_type: str) -> int | None:
    """
    Estimate audio duration in seconds from file content.

    This is a rough estimate based on file size and format.
    Actual duration requires parsing the full audio file.

    Args:
        content: File content as bytes.
        mime_type: Audio MIME type (may include codec params).

    Returns:
        Estimated duration in seconds, or None if cannot estimate.
    """
    size = len(content)
    normalized_type = normalize_mime_type(mime_type)

    # Rough bitrate estimates for common formats
    # These are approximations for estimation purposes
    bitrate_estimates = {
        "audio/wav": 1411000,  # 16-bit stereo 44.1kHz
        "audio/x-wav": 1411000,
        "audio/wave": 1411000,
        "audio/mp3": 128000,   # 128kbps typical
        "audio/mpeg": 128000,
        "audio/mp4": 128000,
        "audio/x-m4a": 128000,
        "audio/webm": 96000,   # Opus typically
        "audio/ogg": 96000,
    }

    bitrate = bitrate_estimates.get(normalized_type)
    if bitrate is None:
        return None

    # Duration = size (bits) / bitrate (bits per second)
    duration_seconds = (size * 8) / bitrate

    return int(duration_seconds)


def generate_audio_filename(visit_id: str, mime_type: str) -> str:
    """
    Generate a standardized filename for storing audio.

    Args:
        visit_id: UUID of the visit.
        mime_type: Audio MIME type (may include codec params).

    Returns:
        Generated filename.
    """
    # Get extension from normalized MIME type
    normalized_type = normalize_mime_type(mime_type)
    extensions = SUPPORTED_AUDIO_TYPES.get(normalized_type, [".webm"])
    extension = extensions[0] if extensions else ".webm"

    return f"{visit_id}{extension}"
