"""add unique constraint to student_competencies

Revision ID: f4e2a1b8c3d5
Revises: ac810655180b
Create Date: 2026-10-12 16:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f4e2a1b8c3d5'
down_revision: Union[str, None] = 'ac810655180b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add (user_id, skill) unique constraint to student_competencies.
    
    F-12 fix: The model declared this constraint as 'added via migration'
    but no migration ever added it. This ensures one competency record
    per user per skill, preventing duplicate rows from concurrent updates.
    
    Safety: First removes any existing duplicates by keeping only the
    most recently updated record for each (user_id, skill) pair.
    """
    # Remove duplicates before adding constraint (keep latest by id)
    op.execute("""
        DELETE FROM student_competencies
        WHERE id NOT IN (
            SELECT MAX(id) FROM student_competencies
            GROUP BY user_id, skill
        )
    """)
    
    op.create_unique_constraint(
        'uq_student_competency_user_skill',
        'student_competencies',
        ['user_id', 'skill']
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_student_competency_user_skill',
        'student_competencies',
        type_='unique'
    )
