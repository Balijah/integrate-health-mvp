"""Add profile picture URL to users table.

Revision ID: 004
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("profile_picture_url", sa.String(500), nullable=True))


def downgrade():
    op.drop_column("users", "profile_picture_url")
