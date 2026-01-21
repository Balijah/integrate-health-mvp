"""Initial database schema.

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-01-15

Creates the initial tables: users, visits, notes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        "users",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Create indexes for users
    op.create_index("idx_users_email", "users", ["email"], unique=True)
    op.create_index(
        "idx_users_active",
        "users",
        ["is_active"],
        postgresql_where=sa.text("is_active = true"),
    )

    # Create visits table
    op.create_table(
        "visits",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("patient_ref", sa.String(255), nullable=False),
        sa.Column("visit_date", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("chief_complaint", sa.Text()),
        sa.Column("audio_file_path", sa.String(500)),
        sa.Column("audio_duration_seconds", sa.Integer()),
        sa.Column("transcript", sa.Text()),
        sa.Column(
            "transcription_status",
            sa.String(50),
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Create indexes for visits
    op.create_index("idx_visits_user_id", "visits", ["user_id"])
    op.create_index("idx_visits_status", "visits", ["transcription_status"])
    op.create_index(
        "idx_visits_date",
        "visits",
        [sa.text("visit_date DESC")],
    )
    op.create_index("idx_visits_patient_ref", "visits", ["patient_ref"])

    # Create notes table
    op.create_table(
        "notes",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "visit_id",
            UUID(as_uuid=True),
            sa.ForeignKey("visits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("note_type", sa.String(50), server_default="soap"),
        sa.Column("status", sa.String(50), server_default="draft"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Create indexes for notes
    op.create_index("idx_notes_visit_id", "notes", ["visit_id"])
    op.create_index("idx_notes_status", "notes", ["status"])
    op.create_index(
        "idx_notes_content_gin",
        "notes",
        ["content"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_table("notes")
    op.drop_table("visits")
    op.drop_table("users")
