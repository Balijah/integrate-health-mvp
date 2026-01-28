"""
Visit model for patient visit records.

Stores visit information including audio files and transcripts.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Visit(Base):
    """
    Visit model representing a patient visit.

    Attributes:
        id: Unique identifier (UUID)
        user_id: Foreign key to users (provider)
        patient_ref: Non-PHI patient identifier
        visit_date: Date and time of visit
        chief_complaint: Main reason for visit
        audio_file_path: Path to stored audio file
        audio_duration_seconds: Length of audio recording
        transcript: Full text transcript from Deepgram
        transcription_status: Status of transcription process
        created_at: Record creation timestamp
        updated_at: Last modification timestamp
    """

    __tablename__ = "visits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_ref: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    visit_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    chief_complaint: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    audio_file_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    audio_duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    transcript: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    transcription_status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        server_default="pending",
        index=True,
    )
    is_live_transcription: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )
    transcription_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("transcription_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="visits",
    )
    notes: Mapped[list["Note"]] = relationship(
        "Note",
        back_populates="visit",
        cascade="all, delete-orphan",
    )
    transcription_sessions: Mapped[list["TranscriptionSession"]] = relationship(
        "TranscriptionSession",
        back_populates="visit",
        cascade="all, delete-orphan",
        foreign_keys="[TranscriptionSession.visit_id]",
    )

    def __repr__(self) -> str:
        return f"<Visit {self.id} - {self.patient_ref}>"
