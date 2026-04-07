"""Add synced_sections to notes table.

Revision ID: 006
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "notes",
        sa.Column(
            "synced_sections",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
    )


def downgrade():
    op.drop_column("notes", "synced_sections")
