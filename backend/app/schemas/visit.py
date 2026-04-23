"""
Visit Pydantic schemas for request/response validation.

Defines schemas for visit creation, updates, and responses.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VisitCreate(BaseModel):
    """Schema for creating a new visit."""

    patient_ref: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Non-PHI patient reference identifier",
    )
    visit_date: datetime = Field(
        ...,
        description="Date and time of the visit",
    )
    chief_complaint: str | None = Field(
        None,
        max_length=1000,
        description="Main reason for the visit",
    )


class VisitUpdate(BaseModel):
    """Schema for updating a visit."""

    patient_ref: str | None = Field(
        None,
        min_length=1,
        max_length=255,
    )
    visit_date: datetime | None = None
    chief_complaint: str | None = Field(None, max_length=1000)


class VisitResponse(BaseModel):
    """Schema for visit data in responses."""

    id: uuid.UUID
    user_id: uuid.UUID
    patient_ref: str
    visit_date: datetime
    chief_complaint: str | None
    audio_file_path: str | None
    audio_duration_seconds: int | None
    transcript: str | None
    transcript_segments: list | None = None
    transcription_status: str
    is_live_transcription: bool
    transcription_session_id: uuid.UUID | None
    all_synced: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VisitListResponse(BaseModel):
    """Schema for paginated visit list response."""

    items: list[VisitResponse]
    total: int
    limit: int
    offset: int


class AudioUploadResponse(BaseModel):
    """Schema for audio upload response."""

    visit_id: uuid.UUID
    audio_file_path: str
    audio_duration_seconds: int | None
    file_size_bytes: int
    mime_type: str
