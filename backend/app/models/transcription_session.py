"""
TranscriptionSession model for live transcription sessions.

Stores live transcription session state and metadata.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TranscriptionSession(Base):
    """
    TranscriptionSession model for live transcription.

    Attributes:
        id: Unique identifier (UUID)
        visit_id: Foreign key to visits
        session_status: Current status (active, paused, completed, failed)
        started_at: When the session started
        ended_at: When the session ended
        total_duration_seconds: Total recording time (excluding pauses)
        pause_count: Number of times paused
        websocket_connection_id: WebSocket connection identifier
        created_at: Record creation timestamp
        updated_at: Last modification timestamp
    """

    __tablename__ = "transcription_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    visit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_status: Mapped[str] = mapped_column(
        String(50),
        default="active",
        server_default="active",
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    total_duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    pause_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
    )
    websocket_connection_id: Mapped[str | None] = mapped_column(
        String(255),
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
    visit: Mapped["Visit"] = relationship(
        "Visit",
        back_populates="transcription_sessions",
        foreign_keys=[visit_id],
    )

    def __repr__(self) -> str:
        return f"<TranscriptionSession {self.id} - {self.session_status}>"
