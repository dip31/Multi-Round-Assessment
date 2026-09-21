"""Add server-authoritative assessment expiry and uniqueness guards."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_assessment_lifecycle_timing"
down_revision: Union[str, Sequence[str], None] = "7b404c6a0d4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    session_columns = {column["name"] for column in inspector.get_columns("assessment_sessions")}
    if "expires_at" not in session_columns:
        op.add_column("assessment_sessions", sa.Column("expires_at", sa.DateTime(), nullable=True))

    round_columns = {column["name"] for column in inspector.get_columns("assessment_rounds")}
    if "expires_at" not in round_columns:
        op.add_column("assessment_rounds", sa.Column("expires_at", sa.DateTime(), nullable=True))

    indexes = {index["name"] for index in inspector.get_indexes("assessment_sessions")}
    if "one_active_session_per_user" not in indexes:
        op.create_index(
            "one_active_session_per_user",
            "assessment_sessions",
            ["user_id"],
            unique=True,
            postgresql_where=sa.text("status = 'in_progress'"),
            sqlite_where=sa.text("status = 'in_progress'"),
        )

    indexes = {index["name"] for index in inspector.get_indexes("assessment_rounds")}
    if "one_active_round_per_session" not in indexes:
        op.create_index(
            "one_active_round_per_session",
            "assessment_rounds",
            ["session_id"],
            unique=True,
            postgresql_where=sa.text("status = 'active'"),
            sqlite_where=sa.text("status = 'active'"),
        )


def downgrade() -> None:
    op.drop_index("one_active_round_per_session", table_name="assessment_rounds")
    op.drop_index("one_active_session_per_user", table_name="assessment_sessions")
    op.drop_column("assessment_rounds", "expires_at")
    op.drop_column("assessment_sessions", "expires_at")
