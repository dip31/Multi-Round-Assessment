"""Add dynamic_interviewers table

Revision ID: add_dynamic_interviewers_table
Revises: becbadd33c98
Create Date: 2026-10-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = 'add_dynamic_interviewers_table'
down_revision = 'becbadd33c98'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'dynamic_interviewers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('tagline', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('personality', sa.Text(), nullable=False),
        sa.Column('speaking_style', sa.Text(), nullable=False),
        sa.Column('greeting', sa.Text(), nullable=False),
        sa.Column('avatar_initials', sa.String(length=10), nullable=False),
        sa.Column('accent', sa.String(length=20), nullable=False),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('voice_id', sa.String(length=100), nullable=False),
        sa.Column('voice_model', sa.String(length=100), nullable=True),
        sa.Column('voice_provider', sa.String(length=50), nullable=False, server_default='retell'),
        sa.Column('language_code', sa.String(length=10), nullable=False, server_default='en-US'),
        sa.Column('pace', sa.Float(), nullable=False, server_default='0.95'),
        sa.Column('retell_llm_id', sa.String(length=100), nullable=True),
        sa.Column('retell_agent_id', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=False), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=False), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_index('ix_dynamic_interviewers_id', 'dynamic_interviewers', ['id'], unique=False)
    op.create_index('ix_dynamic_interviewers_slug', 'dynamic_interviewers', ['slug'], unique=True)
    op.create_index('ix_dynamic_interviewers_retell_agent_id', 'dynamic_interviewers', ['retell_agent_id'], unique=False)


def downgrade():
    op.drop_index('ix_dynamic_interviewers_retell_agent_id', table_name='dynamic_interviewers')
    op.drop_index('ix_dynamic_interviewers_slug', table_name='dynamic_interviewers')
    op.drop_index('ix_dynamic_interviewers_id', table_name='dynamic_interviewers')
    op.drop_table('dynamic_interviewers')