"""
Note model for SOAP notes.

Stores generated SOAP notes in structured JSONB format.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Note(Base):
    """
    Note model representing a SOAP note for a visit.

    Attributes:
        id: Unique identifier (UUID)
        visit_id: Foreign key to visits
        content: JSONB structured SOAP note
        note_type: Type of note (soap, progress, discharge)
        status: Current status (draft, reviewed, finalized)
        created_at: Note creation timestamp
        updated_at: Last modification timestamp
    """

    __tablename__ = "notes"

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
    content: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )
    note_type: Mapped[str] = mapped_column(
        String(50),
        default="soap",
        server_default="soap",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
        server_default="draft",
        index=True,
    )
    synced_sections: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
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
        back_populates="notes",
    )

    def __repr__(self) -> str:
        return f"<Note {self.id} - {self.status}>"
