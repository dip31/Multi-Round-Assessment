"""Add proctoring_events table

Revision ID: add_proctoring_events
Revises:
Create Date: 2026-03-12 10:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_proctoring_events'
down_revision: Union[str, None] = '20260924_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table already created by the 20260924_baseline migration.
    # Guard with inspector so this is a no-op on a fresh database.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    if 'proctoring_events' not in existing_tables:
        op.create_table('proctoring_events',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('session_id', sa.Integer(), nullable=False),
            sa.Column('event_type', sa.String(length=50), nullable=False),
            sa.Column('event_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('NOW()'), nullable=True),
            sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
    indexes = {idx['name'] for idx in inspector.get_indexes('proctoring_events')}
    if 'idx_proctoring_session' not in indexes:
        op.create_index(op.f('idx_proctoring_session'), 'proctoring_events', ['session_id'], unique=False)


def downgrade() -> None:
    # Drop proctoring_events table
    op.drop_index(op.f('idx_proctoring_session'), table_name='proctoring_events')
    op.drop_table('proctoring_events')
