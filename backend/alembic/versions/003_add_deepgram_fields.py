"""Add Deepgram transcription fields to visits.

Revision ID: 003_add_deepgram_fields
Revises: 002_add_live_transcription
Create Date: 2026-03-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003_add_deepgram_fields'
down_revision = '002_add_live_transcription'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('visits', sa.Column('transcription_confidence', sa.Float(), nullable=True))
    op.add_column('visits', sa.Column('num_speakers', sa.Integer(), nullable=True))
    op.add_column('visits', sa.Column('transcript_segments', postgresql.JSONB(), nullable=True))
    op.add_column('visits', sa.Column('transcription_error', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('visits', 'transcription_error')
    op.drop_column('visits', 'transcript_segments')
    op.drop_column('visits', 'num_speakers')
    op.drop_column('visits', 'transcription_confidence')
