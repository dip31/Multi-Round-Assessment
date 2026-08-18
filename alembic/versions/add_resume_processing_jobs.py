"""Add resume_processing_jobs table for asynchronous resume parsing (Stage 6 prep)

Revision ID: add_resume_processing_jobs
Revises: add_production_indexes, merge_sp_violations
Create Date: 2026-08-16

This table is the durable backing store for the asynchronous resume upload
pipeline that Stage 6 will introduce. The HTTP layer will:

    1. upload raw bytes to StorageClient (MinIO) -> write a row with status=PENDING
    2. enqueue a Celery task carrying ONLY {job_id, storage_key} (never raw bytes)
    3. the worker updates status PROCESSING -> COMPLETED / FAILED

The synchronous resume upload endpoint (POST /api/v1/interview/resume/upload)
remains untouched and continues to work — it is NOT modified by this migration
or any model added in this stage. The table exists ahead of time so we can
migrate forward without coupling the schema change to the eventual endpoint
behaviour change.

Manual branching: this SQLAlchemy model lives at app.models.resume_processing.
Two prior heads exist (add_production_indexes and merge_sp_violations);
this migration is intentionally a mergepoint so the linear history is restored.

Status lifecycle (controlled string, not a PG enum — allows extra states
without future migrations):
    PENDING     - row created, not yet claimed
    PROCESSING  - worker claimed the job
    COMPLETED   - ApprovedQuestionPool created and ready for interview
    FAILED      - exhausted retries or unrecoverable error
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_resume_processing_jobs'
# Merge the two existing heads so the history becomes linear again.
down_revision: Union[str, Sequence[str]] = ('add_production_indexes', 'merge_sp_violations')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'resume_processing_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        # Foreign keys to existing tables; cascade on user/session deletion so
        # job rows are cleaned up when the parent records are deleted.
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.Text(), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
        sa.Column('progress_step', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        # Structured metadata as JSONB. Defaults to empty object so the column
        # is always JSON-typed even when no metadata is supplied.
        sa.Column('job_metadata', postgresql.JSONB(astext_type=sa.Text()),
                  server_default='{}', nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Indexes — keep this small and intentional. The four indexes below cover
    # the dominant query paths:
    #   - lookup-by-user (per-user job history)
    #   - lookup-by-session (the assessment flow's most common access pattern)
    #   - lookup-by-status (worker claiming a PENDING job, retry-on-FAILED)
    #   - created_at ordering (recent jobs first)
    # No composite indexes. Composite indexes should be added only after we
    # see a real query pattern in Stage 6 traffic, not ahead of time.
    op.create_index(
        op.f('ix_resume_processing_jobs_user_id'),
        'resume_processing_jobs', ['user_id'], unique=False,
    )
    op.create_index(
        op.f('ix_resume_processing_jobs_session_id'),
        'resume_processing_jobs', ['session_id'], unique=False,
    )
    op.create_index(
        op.f('ix_resume_processing_jobs_status'),
        'resume_processing_jobs', ['status'], unique=False,
    )
    op.create_index(
        op.f('ix_resume_processing_jobs_created_at'),
        'resume_processing_jobs', ['created_at'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_resume_processing_jobs_created_at'),
                  table_name='resume_processing_jobs')
    op.drop_index(op.f('ix_resume_processing_jobs_status'),
                  table_name='resume_processing_jobs')
    op.drop_index(op.f('ix_resume_processing_jobs_session_id'),
                  table_name='resume_processing_jobs')
    op.drop_index(op.f('ix_resume_processing_jobs_user_id'),
                  table_name='resume_processing_jobs')
    op.drop_table('resume_processing_jobs')
