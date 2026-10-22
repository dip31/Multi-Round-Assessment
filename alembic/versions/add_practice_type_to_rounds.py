"""add practice_type to assessment_rounds

Revision ID: add_practice_type_rounds
Revises: 545b4e6f20d4
Create Date: 2026-09-24 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_practice_type_rounds'
down_revision = '545b4e6f20d4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col['name'] for col in inspector.get_columns('assessment_rounds')}
    if 'practice_type' not in existing_cols:
        op.add_column(
            'assessment_rounds',
            sa.Column('practice_type', sa.String(length=20), nullable=True)
        )


def downgrade() -> None:
    op.drop_column('assessment_rounds', 'practice_type')
