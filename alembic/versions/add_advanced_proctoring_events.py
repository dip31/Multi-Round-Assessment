"""Add advanced proctoring events table

Revision ID: add_advanced_proctoring_events
Revises: add_proctoring_events
Create Date: 2024-01-01 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_advanced_proctoring_events'
down_revision = 'add_proctoring_events'
branch_labels = None
depends_on = None


def upgrade():
    # Table already created by the 20260924_baseline migration.
    # Guard with inspector so this is a no-op on a fresh database.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    if 'advanced_proctoring_events' not in existing_tables:
        op.create_table('advanced_proctoring_events',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('session_id', sa.Integer(), nullable=False),
            sa.Column('event_type', sa.String(length=50), nullable=False),
            sa.Column('confidence', sa.Float(), nullable=True),
            sa.Column('event_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['session_id'], ['assessment_sessions.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
    indexes = {idx['name'] for idx in inspector.get_indexes('advanced_proctoring_events')}
    for idx_name, col in [
        ('ix_advanced_proctoring_events_id', ['id']),
        ('ix_advanced_proctoring_events_session_id', ['session_id']),
        ('ix_advanced_proctoring_events_event_type', ['event_type']),
        ('ix_advanced_proctoring_events_created_at', ['created_at']),
    ]:
        if idx_name not in indexes:
            op.create_index(op.f(idx_name), 'advanced_proctoring_events', col, unique=False)


def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_advanced_proctoring_events_created_at'), table_name='advanced_proctoring_events')
    op.drop_index(op.f('ix_advanced_proctoring_events_event_type'), table_name='advanced_proctoring_events')
    op.drop_index(op.f('ix_advanced_proctoring_events_session_id'), table_name='advanced_proctoring_events')
    op.drop_index(op.f('ix_advanced_proctoring_events_id'), table_name='advanced_proctoring_events')

    # Drop table
    op.drop_table('advanced_proctoring_events')
