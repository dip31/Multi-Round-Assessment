"""Add proctoring_violations table

Revision ID: add_proctoring_violations
Revises: add_interview_tables
Create Date: 2026-03-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_proctoring_violations'
down_revision: Union[str, None] = 'add_role_detection'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create proctoring_violations table
    op.create_table('proctoring_violations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('face_count', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['interview_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_violations_session', 'proctoring_violations', ['session_id', 'created_at'], unique=False)


def downgrade() -> None:
    # Drop table and index
    op.drop_index('idx_violations_session', table_name='proctoring_violations')
    op.drop_table('proctoring_violations')
