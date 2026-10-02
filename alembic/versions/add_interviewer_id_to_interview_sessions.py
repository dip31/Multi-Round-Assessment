"""Add interviewer_id to interview_sessions

Records which interviewer persona the candidate selected. Presentation only —
it does not participate in scoring, question selection, or RL state.

Nullable with no backfill and no default. NULL means "no choice recorded",
which the application resolves to the default profile, so every session that
predates interviewer selection keeps working untouched. Backfilling would be
actively wrong: it would assert those candidates made a choice they never made.

Revision ID: add_interviewer_id_001
Revises: link_interview_rounds
Create Date: 2026-09-30 00:00:00.000000

NOTE: this repository has two Alembic heads (``link_interview_rounds`` and the
orphaned ``20260924_baseline``), so ``alembic upgrade head`` fails with
"Multiple head revisions are present". This revision deliberately chains off
``link_interview_rounds`` — the head of the real incremental chain. Apply it by
targeting the revision explicitly:

    alembic upgrade add_interviewer_id_001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_interviewer_id_001'
down_revision: Union[str, None] = 'link_interview_rounds'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No FK: the interviewer roster is a config module, not a table.
    op.add_column(
        'interview_sessions',
        sa.Column('interviewer_id', sa.String(length=50), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('interview_sessions', 'interviewer_id')
