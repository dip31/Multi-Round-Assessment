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
    # Create advanced_proctoring_events table
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
    
    # Create indexes
    op.create_index(op.f('ix_advanced_proctoring_events_id'), 'advanced_proctoring_events', ['id'], unique=False)
    op.create_index(op.f('ix_advanced_proctoring_events_session_id'), 'advanced_proctoring_events', ['session_id'], unique=False)
    op.create_index(op.f('ix_advanced_proctoring_events_event_type'), 'advanced_proctoring_events', ['event_type'], unique=False)
    op.create_index(op.f('ix_advanced_proctoring_events_created_at'), 'advanced_proctoring_events', ['created_at'], unique=False)


def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_advanced_proctoring_events_created_at'), table_name='advanced_proctoring_events')
    op.drop_index(op.f('ix_advanced_proctoring_events_event_type'), table_name='advanced_proctoring_events')
    op.drop_index(op.f('ix_advanced_proctoring_events_session_id'), table_name='advanced_proctoring_events')
    op.drop_index(op.f('ix_advanced_proctoring_events_id'), table_name='advanced_proctoring_events')
    
    # Drop table
    op.drop_table('advanced_proctoring_events')
