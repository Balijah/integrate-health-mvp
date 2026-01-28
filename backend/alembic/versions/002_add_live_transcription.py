"""Add live transcription support.

Revision ID: 002_add_live_transcription
Revises: 001_initial_schema
Create Date: 2024-01-27

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '002_add_live_transcription'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create transcription_sessions table
    op.create_table(
        'transcription_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('visit_id', UUID(as_uuid=True), sa.ForeignKey('visits.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_status', sa.String(50), server_default='active', nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('pause_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('websocket_connection_id', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Create indexes for transcription_sessions
    op.create_index('idx_transcription_session_visit', 'transcription_sessions', ['visit_id'])
    op.create_index('idx_transcription_session_status', 'transcription_sessions', ['session_status'])

    # Add columns to visits table
    op.add_column('visits', sa.Column('is_live_transcription', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('visits', sa.Column('transcription_session_id', UUID(as_uuid=True), nullable=True))

    # Add foreign key constraint for transcription_session_id
    op.create_foreign_key(
        'fk_visits_transcription_session',
        'visits', 'transcription_sessions',
        ['transcription_session_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Drop foreign key constraint
    op.drop_constraint('fk_visits_transcription_session', 'visits', type_='foreignkey')

    # Drop columns from visits table
    op.drop_column('visits', 'transcription_session_id')
    op.drop_column('visits', 'is_live_transcription')

    # Drop indexes
    op.drop_index('idx_transcription_session_status', 'transcription_sessions')
    op.drop_index('idx_transcription_session_visit', 'transcription_sessions')

    # Drop transcription_sessions table
    op.drop_table('transcription_sessions')
